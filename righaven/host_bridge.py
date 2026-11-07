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
OPTIONAL = {'home', 'hint', 'key', 'confirm'}
# Writes to a device: only the chat tool asks them, after the owner approved that exact write.
APPROVED_ONLY = {'ble-write'}
ARGUMENTS = {'busid': re.compile(r'[0-9]{1,3}-[0-9]{1,3}(\.[0-9]{1,3})*\Z'), 'name': re.compile(r'COM[0-9]{1,3}\Z'),
             'address': re.compile(r'[0-9A-F]{2}(:[0-9A-F]{2}){5}\Z'),
             'service': re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z'),
             'characteristic': re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z'),
             'value': re.compile(r'([0-9a-f]{2}){1,512}\Z'),
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
        elif key in ('service', 'characteristic'):
            value = uuid128(value)
        elif key == 'value':
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
