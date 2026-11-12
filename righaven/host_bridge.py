"""Actions on the PC itself, asked from the RigHaven page and carried out by the launcher.

Inside WSL or a container RigHaven cannot reach the PC's Bluetooth, USB ports, COM ports or WSL
settings. The launcher (RigHaven.exe, or the Linux launcher's agent) is running next to RigHaven:
it polls a shared folder, runs the request on the PC and writes the result back. The owner's
click on the page is the request; Windows may still ask its own permission (administrator
prompt) for the changes that need it.
"""
import json
import os
from pathlib import Path
import re
import time
import uuid

HOST_DIR = '/run/righaven/host'
ACTIONS = {
    'bluetooth-scan': (), 'wifi-scan': (), 'usb-list': (), 'usb-install': (), 'usb-attach': ('busid', 'confirm'), 'usb-detach': ('busid',), 'com-list': (),
    'com-share': ('name',), 'matter-enable': (), 'matter-disable': (), 'refresh-devices': (),
    'ble-inspect': ('address',), 'ble-read': ('address', 'service', 'characteristic'),
    'ble-write': ('address', 'service', 'characteristic', 'value'),
    # Commands written in one connection while the notify characteristic is listened to (OBD-II
    # adapters and serial bridges answer only by notification).
    'ble-exchange': ('address', 'service', 'characteristic', 'notify', 'commands', 'until', 'wait'),
    # The home Wi-Fi to a device in setup mode: the password, typed by the owner in the page, is
    # used for this request only (the launcher does not store or return it).
    'wifi-provision': ('ssid', 'hint', 'password', 'home'),
    # Any Wi-Fi network the owner chooses: joined for a few seconds to read what answers there.
    'wifi-explore': ('ssid', 'hint', 'key'),
    'pc-devices': (), 'net-listen': (), 'lan-devices': (),
    # Agents on a phone: one NFC tag held to the phone, read only (the app on screen reads it).
    'nfc-read': (),
    # Agents only: the home network searched from the agent (the server cannot see it).
    'net-scan': ('network',),
    # Agents only: whether a host of the agent's network (a database, a device) answers on a port.
    'tcp-check': ('target',),
    # The owner's own recording of the PC's traffic (Windows asks for administrator rights).
    'traffic-capture': ('seconds',),
}
OPTIONAL = {'home', 'hint', 'key', 'confirm', 'notify', 'until', 'wait'}
# Writes to a device: only the chat tool asks them, after the owner approved that exact write.
APPROVED_ONLY = {'ble-write', 'ble-exchange'}
ARGUMENTS = {'busid': re.compile(r'[0-9]{1,3}-[0-9]{1,3}(\.[0-9]{1,3})*\Z'), 'name': re.compile(r'COM[0-9]{1,3}\Z'),
             'address': re.compile(r'[0-9A-F]{2}(:[0-9A-F]{2}){5}\Z'),
             'service': re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z'),
             'characteristic': re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z'),
             'value': re.compile(r'([0-9a-f]{2}){1,512}\Z'),
             'notify': re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z'),
             'commands': re.compile(r'([0-9a-f]{2}){1,64}(,([0-9a-f]{2}){1,64}){0,15}\Z'),
             'until': re.compile(r'[0-9a-f]{2}\Z'), 'wait': re.compile(r'([2-9]\d\d|[1-9]\d{3}|10000)\Z'),
             'ssid': re.compile(r'[^\x00-\x1f\x7f]{1,32}\Z'), 'home': re.compile(r'[^\x00-\x1f\x7f]{1,32}\Z'),
             'hint': re.compile(r'(tasmota|shelly|esp|wled|openbeken|tuya|daikin|lg|direct)\Z'), 'password': re.compile(r'[^\x00-\x1f\x7f]{8,63}\Z'),
             'key': re.compile(r'[^\x00-\x1f\x7f]{8,63}\Z'),
             'network': re.compile(r'(10|172|192)\.\d{1,3}\.\d{1,3}\.\d{1,3}/(2[0-9]|3[0-2]|1[6-9])\Z'),
             # host:port of the agent's network: a private IP or an internal name the agent resolves.
             'target': re.compile(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}:[0-9]{1,5}\Z'),
             'seconds': re.compile(r'(1\d|[2-9]\d|[1-9]\d\d|1[0-7]\d\d|1800)\Z'), 'confirm': re.compile(r'yes\Z')}


def uuid128(value):
    """Bluetooth UUIDs as Windows wants them: 180a or 0x180A becomes 0000180a-0000-1000-8000-00805f9b34fb."""
    text = str(value or '').strip().lower().removeprefix('0x')
    if re.fullmatch(r'[0-9a-f]{4}|[0-9a-f]{8}', text):
        return text.rjust(8, '0') + '-0000-1000-8000-00805f9b34fb'
    return text
HEARTBEAT_SECONDS = 15


def folder():
    return Path(os.getenv('RIGHAVEN_HOST_DIR', HOST_DIR))


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # a request may carry a Wi-Fi password
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(json.dumps(value))
    temporary.replace(path)


def state(agent=None):
    """Whether the launcher (or the given agent) answers, on which platform, and what it can do there."""
    if agent:
        from . import agent_hub
        return agent_hub.state(agent)
    base = folder()
    try:
        heartbeat = json.loads((base / 'heartbeat.json').read_text())
        age = time.time() - float(heartbeat.get('at', 0))
    except (OSError, ValueError, TypeError):
        return {'connected': False, 'platform': '', 'actions': []}
    platform = heartbeat.get('platform') if heartbeat.get('platform') in ('windows', 'linux') else ''
    actions = [a for a in heartbeat.get('actions') or [] if a in ACTIONS]
    return {'connected': 0 <= age <= HEARTBEAT_SECONDS, 'platform': platform, 'actions': actions,
            'matter': heartbeat.get('matter') is True}


def request(action, args=None, agent=None):
    if action not in ACTIONS:
        raise ValueError('Azione sul PC non disponibile')
    args = args or {}
    clean = {}
    for key in ACTIONS[action]:
        value = str(args.get(key, '')) if key in ('password', 'key') else str(args.get(key, '')).strip()
        if key in OPTIONAL and not value:
            continue
        if key == 'address':
            value = value.upper().replace('-', ':')
        elif key in ('service', 'characteristic', 'notify'):
            value = uuid128(value)
        elif key in ('value', 'commands', 'until'):
            value = value.lower().replace(' ', '').removeprefix('0x')
        if not ARGUMENTS[key].fullmatch(value):
            raise ValueError('Parametro non valido per ' + action + ': ' + key)
        clean[key] = value
    if agent:
        from . import agent_hub
        return agent_hub.request(agent, action, clean)
    if action in ('net-scan', 'tcp-check'):
        raise ValueError('Questa azione non è disponibile su questo PC')
    current = state()
    if not current['connected']:
        raise ValueError('Il launcher di RigHaven non risponde: tieni aperta la finestra di RigHaven sul PC')
    if action not in current['actions']:
        raise ValueError('Questa azione non è disponibile su questo PC')
    identifier = uuid.uuid4().hex
    _write(folder() / 'requests' / (identifier + '.json'), {'id': identifier, 'action': action, 'args': clean, 'at': time.time()})
    return {'id': identifier, 'status': 'queued'}


def result(identifier):
    if not re.fullmatch(r'[0-9a-f]{32}', str(identifier)):
        raise ValueError('Richiesta non valida')
    from . import agent_hub
    remote = agent_hub.result(identifier)
    if remote is not None:
        return remote
    base = folder()
    try:
        value = json.loads((base / 'results' / (identifier + '.json')).read_text()[:2_000_000])
        return {'id': identifier, 'status': 'failed' if value.get('error') else 'done', 'result': value}
    except (OSError, ValueError):
        pass
    if (base / 'requests' / (identifier + '.json')).exists():
        return {'id': identifier, 'status': 'queued'}
    if (base / 'running' / (identifier + '.json')).exists():
        return {'id': identifier, 'status': 'running'}
    return {'id': identifier, 'status': 'unknown'}


class SeveralPCs(ValueError):
    """Several of the owner's PCs are connected and none was named."""


def pick(user, agent=None):
    """Which PC a chat tool uses: the agent named (its ID or its name), else the launcher next to this
    server, else the user's only agent online. With several online the owner chooses: never a guess."""
    from . import agent_hub, agents
    rows = agents.listing(user)
    if agent:
        text = str(agent).strip()
        named = [r for r in rows if r['id'] == text or r['name'].casefold() == text.casefold()]
        if len(named) != 1:
            agents.owned(user, text)  # the usual "not found" for an unknown ID or name
        return named[0]['id']
    if state()['connected']:
        return None
    online = [r for r in rows if agent_hub.online(r['id'])]
    if len(online) == 1:
        return online[0]['id']
    if online:
        raise SeveralPCs('Più PC collegati: indica quale usare (agent): ' + ', '.join(f"{r['name']} ({r['id']})" for r in online))
    raise ValueError('Nessun PC collegato: apri RigHaven sul PC, oppure collega un PC con RigHaven Agent (Connessioni → Agenti)')


def run(action, args=None, timeout=180, poll=2.0, agent=None):
    """Ask the launcher or an agent and wait for its answer (used by the chat tools)."""
    job = request(action, args, agent)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll)
        status = result(job['id'])
        if status['status'] == 'done':
            return status['result']
        if status['status'] == 'failed':
            raise ValueError(str(status['result'].get('error') or 'Azione sul PC non riuscita')[:500])
    raise ValueError('Il launcher non ha risposto in tempo: ' + action)


def bluetooth_exchange(row, agent, command, notify='', until='', wait=3000):
    """One approved write and what the device notifies back, in the same connection (the bytes are not interpreted)."""
    if len(command['payload']) > 128:
        raise ValueError('exchange sends at most 64 bytes: use write for longer values')
    service, _, characteristic = command['address'].partition('/')
    if not 200 <= int(wait) <= 10000:
        raise ValueError('wait: from 200 to 10000 milliseconds')
    args = {'address': row['address'], 'service': service, 'characteristic': characteristic, 'notify': notify,
            'commands': command['payload'], 'wait': str(int(wait))}
    if until:
        end = until.encode()
        args['until'] = end[-1:].hex()  # the agent stops at the last byte of the end marker
    if bluetooth_busy(agent, row['address']):
        raise ValueError('The Bluetooth device is in use by a task now (one client at a time): wait for it to end, or use the task to send the command')
    try:
        answer = run('ble-exchange', args, timeout=120, agent=agent)
    except ValueError as error:
        if 'non è disponibile' in str(error):
            raise ValueError('This RigHaven Agent (or app) is too old to listen to Bluetooth notifications: update it from the latest release, then retry') from error
        raise
    notified = (answer.get('responses') or [''])[0]
    try:
        shown = bytes.fromhex(notified).decode('utf-8', 'replace')
    except ValueError:
        shown = ''
    return {'notified': notified, 'text': shown}


# Serial-over-BLE profiles of common modules and adapters (service, write, notify): the same list
# and the same choice as RigHaven Agent's channels, so the chat and the tasks use one channel.
PROFILES = (
    ('0000fff0-0000-1000-8000-00805f9b34fb', '0000fff2-0000-1000-8000-00805f9b34fb', '0000fff1-0000-1000-8000-00805f9b34fb'),
    ('0000ffe0-0000-1000-8000-00805f9b34fb', '0000ffe1-0000-1000-8000-00805f9b34fb', '0000ffe1-0000-1000-8000-00805f9b34fb'),
    ('000018f0-0000-1000-8000-00805f9b34fb', '00002af1-0000-1000-8000-00805f9b34fb', '00002af0-0000-1000-8000-00805f9b34fb'),
    ('6e400001-b5a3-f393-e0a9-e50e24dcca9e', '6e400002-b5a3-f393-e0a9-e50e24dcca9e', '6e400003-b5a3-f393-e0a9-e50e24dcca9e'),
    ('e7810a71-73ae-499d-8c15-faa9aef0c3f2', 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f', 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f'),
)


def choose_channel(services):
    """The channel profile of a device from ble-inspect: a known serial profile it has, else the first
    service (not a standard 18xx one) with a characteristic that takes writes and one that notifies."""
    found = {str(s.get('uuid', '')).lower(): {str(c.get('uuid', '')).lower(): set(c.get('properties') or []) for c in s.get('characteristics') or []}
             for s in services or []}
    for service, write, notify in PROFILES:
        if write in found.get(service, {}) and notify in found.get(service, {}):
            return service, write, notify
    for service, characteristics in found.items():
        if service.startswith('000018') and service.endswith('-0000-1000-8000-00805f9b34fb') and not service.startswith('000018f0'):
            continue
        writes = [u for u, p in characteristics.items() if p & {'Write', 'WriteWithoutResponse'}]
        notifies = [u for u, p in characteristics.items() if p & {'Notify', 'Indicate'}]
        if writes and notifies:
            return service, writes[0], notifies[0]
    raise ValueError('No service of this Bluetooth device takes writes and notifies: name the channel profile (service, write, notify)')


def bluetooth_busy(agent, address):
    """A task holds this Bluetooth device now (one client at a time)."""
    if not agent:
        return False
    from . import agent_hub
    return agent_hub.in_use(agent, 'ble:' + str(address).upper())
