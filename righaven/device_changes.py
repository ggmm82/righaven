"""The owner's approval of each write to an external device.

Reading never needs it. Every write does: a command (MQTT, Modbus, HTTP, serial, TCP),
firmware, an Android app or update, a reboot, clearing vehicle trouble codes. The coordinator
asks for one precise change (device, action, file digest, package or exact command); the
owner approves or rejects it in the task card; the approval is delivered once, to the next
assignment that receives that device, and the iot toolkit refuses any write that does not
match it exactly.
"""
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

from . import state

FILE = 'device-changes.json'
ACTIONS = {'flash': ('file', '.bin'), 'sideload': ('file', '.zip'), 'install': ('file', '.apk'),
           'uninstall': ('package', None), 'disable': ('package', None), 'enable': ('package', None), 'reboot': ('mode', None),
           'send': ('command', None), 'clear_codes': ('none', None), 'scan': ('scope', None)}
SCAN_PROFILES = ('safe', 'tls')
# The fields of iot.send that define what is written; defaults are dropped so equal commands match.
COMMAND_FIELDS = ('payload', 'encoding', 'topic', 'retain', 'method', 'address', 'values', 'coil')
COMMAND_DEFAULTS = {'encoding': 'text', 'retain': False, 'coil': False, 'method': 'POST'}
MODES = ('system', 'recovery', 'bootloader', 'sideload')
PACKAGE = re.compile(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+\Z')
MAX_FILE = 4 * 1024 ** 3
MAX_PENDING = 10
WORKSPACE_ROOT = '/mnt/user-data/'


def command_fingerprint(command):
    """Same function as iot_job.command_fingerprint: the approved command and the executed one must match."""
    value = {k: command[k] for k in COMMAND_FIELDS if k in command and command[k] is not None and COMMAND_DEFAULTS.get(k, object()) != command[k]}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def scope_fingerprint(targets, profile):
    """Same function as netscan_job.scope_fingerprint: the approved scan and the executed one must match."""
    value = {'targets': sorted(str(t) for t in targets), 'profile': profile}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def bluetooth_command(command):
    """A Bluetooth LE write as iot.send fields: payload in hex, address service/characteristic (full UUIDs)."""
    from .host_bridge import ARGUMENTS, uuid128
    command = dict(command or {})
    service, _, characteristic = str(command.get('address') or '').partition('/')
    value = {'payload': str(command.get('payload') or '').lower().replace(' ', '').removeprefix('0x'), 'encoding': 'hex',
             'address': uuid128(service) + '/' + uuid128(characteristic)}
    if set(command) - {'payload', 'encoding', 'address'} or command.get('encoding', 'hex') != 'hex' \
            or not ARGUMENTS['service'].fullmatch(uuid128(service)) or not ARGUMENTS['characteristic'].fullmatch(uuid128(characteristic)) \
            or not ARGUMENTS['value'].fullmatch(value['payload']):
        raise ValueError('Bluetooth LE write: payload in hexadecimal bytes, encoding hex, address service/characteristic UUIDs')
    return value


def consume(workspace, connection, fingerprint):
    """Use one approved write of the coordinator's own tools (Bluetooth LE): once, and only that exact write."""
    from .project_store import locked
    with locked(workspace) as directory:
        changes = _load(directory)
        change = next((c for c in changes if c['connection'] == connection and c['status'] == 'approved' and c.get('fingerprint') == fingerprint), None)
        if change is None:
            return None
        change.update(status='delivered', delivered_at=_now(), job='coordinator')
        state.atomic_json(Path(directory) / FILE, changes)
    return change


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _load(directory):
    path = Path(directory) / FILE
    if not path.is_file() or path.is_symlink():
        return []
    value = json.loads(path.read_text())
    return value if isinstance(value, list) else []


def _file(workspace, value):
    """A file the team produced or the owner attached, inside this conversation only."""
    text = str(value or '').strip()
    if text.startswith(WORKSPACE_ROOT):
        text = text[len(WORKSPACE_ROOT):]
    workspace = Path(workspace).resolve()
    path = (workspace / text).resolve()
    if not text or not path.is_relative_to(workspace) or not path.is_file():
        raise ValueError('The file of a device change must be saved in this conversation: ' + str(value))
    if path.stat().st_size > MAX_FILE:
        raise ValueError('The file of a device change is larger than 4 GiB')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return path, digest.hexdigest()


def request(workspace, connection, action, file_path='', package='', mode='', note='', command=None, targets=None, profile=''):
    """Record one change for the owner to decide; nothing reaches the device yet."""
    if action not in ACTIONS:
        raise ValueError('Device change: ' + ', '.join(ACTIONS))
    from .connections import assigned
    row = next((c for c in assigned(workspace) if c.get('id') == connection), None)
    if not row or row.get('kind') not in ('device', 'network') or (row.get('kind') == 'network') != (action == 'scan'):
        raise ValueError('Ask device changes only for a device connection assigned to the task: ' + str(connection))
    if not row.get('write'):
        raise ValueError('The owner has not allowed writing on this device for the task: ask for that first')
    if action in ('sideload', 'install', 'uninstall', 'disable', 'enable', 'reboot') and row.get('protocol') != 'adb':
        raise ValueError('This change needs an Android device connection (ADB): ' + action)
    if row.get('transport') == 'bluetooth':
        if action != 'send':
            raise ValueError('A Bluetooth LE device accepts only send: a write of bytes to one characteristic')
        command = bluetooth_command(command)
    if action == 'flash' and row.get('transport') not in ('serial', 'local'):
        raise ValueError('Flashing needs a serial device connection (local port or RFC 2217)')
    kind, suffix = ACTIONS[action]
    change = {'id': uuid.uuid4().hex[:12], 'connection': connection, 'device': row.get('name', connection), 'action': action,
              'note': str(note or '').strip()[:600], 'status': 'pending', 'requested_at': _now()}
    if kind == 'file':
        path, digest = _file(workspace, file_path)
        if path.suffix.lower() != suffix:
            raise ValueError('This change needs a ' + suffix + ' file')
        change.update(file=path.name, path=str(path.relative_to(Path(workspace).resolve())), size=path.stat().st_size, sha256=digest)
    elif kind == 'command':
        if not isinstance(command, dict) or not command or set(command) - set(COMMAND_FIELDS):
            raise ValueError('Describe the command with the iot.send fields: ' + ', '.join(COMMAND_FIELDS))
        shown = {k: v for k, v in command.items() if v is not None}
        if len(json.dumps(shown)) > 4000:
            raise ValueError('The command to approve is longer than 4000 characters')
        change.update(command=shown, fingerprint=command_fingerprint(command))
    elif kind == 'none':
        pass
    elif kind == 'scope':
        import ipaddress
        from .connections import scan_ranges
        if profile not in SCAN_PROFILES:
            raise ValueError('Scan profile: ' + ', '.join(SCAN_PROFILES))
        wanted = scan_ranges(targets or row.get('ranges', []), 'obiettivi')
        allowed = [ipaddress.ip_network(r) for r in row.get('ranges', [])]
        outside = [str(t) for t in wanted if not any(t.version == a.version and t.subnet_of(a) for a in allowed)]
        if not wanted or outside:
            raise ValueError('Scan targets must be inside the authorized networks of the connection: ' + ', '.join(outside[:5]))
        change.update(command={'targets': [str(t) for t in wanted], 'profile': profile, 'exclude': row.get('exclude', [])},
                      fingerprint=scope_fingerprint(wanted, profile))
    elif kind == 'package':
        if not PACKAGE.fullmatch(str(package or '')):
            raise ValueError('Name the Android package, for example com.example.app')
        change['package'] = package
    else:
        if mode not in MODES:
            raise ValueError('Reboot mode: ' + ', '.join(MODES))
        change['mode'] = mode
    from .project_store import locked
    with locked(workspace) as directory:
        changes = _load(directory)
        if sum(1 for c in changes if c['status'] == 'pending') >= MAX_PENDING:
            raise ValueError('Too many device changes wait for the owner: let them decide first')
        changes.append(change)
        state.atomic_json(Path(directory) / FILE, changes[-100:])
    from .audit_log import append
    append(workspace, 'Dispositivi', 'Riprogrammazione richiesta al proprietario', 'pending', _summary(change))
    return change


def decide(workspace, identifier, decision):
    if decision not in ('approve', 'reject'):
        raise ValueError('Decision: approve or reject')
    from .project_store import locked
    with locked(workspace) as directory:
        changes = _load(directory)
        change = next((c for c in changes if c['id'] == identifier), None)
        if not change:
            raise ValueError('Device change not found: ' + str(identifier))
        if change['status'] != 'pending':
            raise ValueError('This device change was already decided')
        if decision == 'approve' and change.get('path'):
            # The approved file is the file the owner saw: it must not have changed since the request.
            _, digest = _file(workspace, change['path'])
            if digest != change['sha256']:
                change.update(status='rejected', decided_at=_now(), reason='file changed after the request')
                state.atomic_json(Path(directory) / FILE, changes)
                raise ValueError('The file changed after the request: ask again')
        change.update(status='approved' if decision == 'approve' else 'rejected', decided_at=_now())
        state.atomic_json(Path(directory) / FILE, changes)
    from .audit_log import append
    append(workspace, 'Dispositivi', 'Riprogrammazione approvata' if decision == 'approve' else 'Riprogrammazione rifiutata', 'completed', _summary(change))
    return change


def listing(workspace):
    from .project_store import locked
    with locked(workspace) as directory:
        return list(reversed(_load(directory)))[:30]


def deliver(workspace, connection, job):
    """Approved changes of this device, handed once to one assignment."""
    from .project_store import locked
    delivered = []
    with locked(workspace) as directory:
        changes = _load(directory)
        for change in changes:
            if change['connection'] == connection and change['status'] == 'approved':
                change.update(status='delivered', delivered_at=_now(), job=str(job))
                delivered.append({k: change[k] for k in ('id', 'action', 'sha256', 'package', 'mode', 'file', 'fingerprint') if k in change})
        if delivered:
            state.atomic_json(Path(directory) / FILE, changes)
    return delivered


def _summary(change):
    detail = (change.get('file', '') + (' · sha256 ' + change['sha256'][:12] if change.get('sha256') else '') or change.get('package') or change.get('mode')
              or (json.dumps(change['command'], ensure_ascii=False)[:200] if change.get('command') else ''))
    return f"{change['connection']} · {change['action']} · {detail}"
