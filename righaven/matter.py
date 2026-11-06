"""Matter devices through the optional Matter controller (python-matter-server).

RigHaven joins devices that are already set up in another app (Alexa, SmartThings, Google Home,
Apple Home) with the pairing code that app shows when it shares the device ("multi-admin"):
the device keeps working there. The controller runs on the PC with the host network, because
Matter finds devices with multicast and IPv6 on the local network.
"""
import json
import os
import re
import time
import uuid

# Clusters read into a short summary: (endpoint attribute path suffix, name, factor, unit)
READINGS = {
    (6, 0): ('on', None, ''), (8, 0): ('level', None, ''), (1026, 0): ('temperature', 0.01, '°C'),
    (1029, 0): ('humidity', 0.01, '%'), (1030, 0): ('occupancy', None, ''), (69, 0): ('contact', None, ''),
    (1024, 0): ('illuminance', None, 'lx'), (1027, 0): ('pressure', 0.1, 'kPa'), (47, 12): ('battery', 0.5, '%'),
}
COMMANDS = {'On': (6, 'On'), 'Off': (6, 'Off'), 'Toggle': (6, 'Toggle')}
CODE = re.compile(r'(MT:[0-9A-Z.\-]{19,})|([0-9]{11}|[0-9]{21})\Z')


def url():
    return os.getenv('RIGHAVEN_MATTER_URL', '').strip()


def available():
    return bool(url())


def call(command, args=None, timeout=30):
    """One request to the controller's WebSocket API."""
    if not available():
        raise ValueError('Il controller Matter non è attivo: sul PC esegui RigHaven.exe matter enable (Windows) o ./righaven --matter (Linux)')
    from websockets.sync.client import connect
    deadline = time.monotonic() + timeout
    try:
        with connect(url(), open_timeout=5, close_timeout=2, max_size=16 * 1024 * 1024) as socket:
            socket.recv(timeout=10)  # server information
            identifier = uuid.uuid4().hex
            socket.send(json.dumps({'message_id': identifier, 'command': command, 'args': args or {}}))
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('Il controller Matter non ha risposto in tempo')
                message = json.loads(socket.recv(timeout=remaining))
                if message.get('message_id') != identifier:
                    continue  # events of other nodes
                if 'error_code' in message:
                    raise ValueError('Matter: ' + str(message.get('details') or message['error_code'])[:300])
                return message.get('result')
    except (OSError, TimeoutError) as error:
        raise RuntimeError('Controller Matter non raggiungibile: ' + str(error)[:200]) from None


def summary(node):
    attributes = node.get('attributes') or {}
    def attribute(path):
        return attributes.get(path)
    endpoints = sorted({int(path.split('/')[0]) for path in attributes if path.split('/')[0].isdigit()})
    readings = {}
    for endpoint in endpoints:
        for (cluster, attr), (name, factor, unit) in READINGS.items():
            value = attribute(f'{endpoint}/{cluster}/{attr}')
            if value is None:
                continue
            if factor and isinstance(value, (int, float)):
                value = round(value * factor, 2)
            key = name if endpoint in (0, 1) or name not in readings else f'{name}_{endpoint}'
            readings[key] = {'value': value, 'unit': unit, 'endpoint': endpoint} if unit else {'value': value, 'endpoint': endpoint}
    switchable = [e for e in endpoints if attribute(f'{e}/6/0') is not None]
    name = attribute('0/40/5') or attribute('0/40/3') or f"Matter {node.get('node_id')}"
    return {'node_id': node.get('node_id'), 'available': bool(node.get('available')), 'name': str(name)[:80],
            'vendor': str(attribute('0/40/1') or '')[:60], 'product': str(attribute('0/40/3') or '')[:60],
            'readings': readings, 'switchable': switchable}


def status():
    if not available():
        return {'available': False, 'nodes': []}
    try:
        nodes = call('get_nodes') or []
    except (RuntimeError, ValueError) as error:
        return {'available': True, 'reachable': False, 'error': str(error), 'nodes': []}
    return {'available': True, 'reachable': True, 'url': url(), 'nodes': [summary(n) for n in nodes if isinstance(n, dict)]}


def commission(code):
    code = re.sub(r'[\s-]', '', str(code or '')) if not str(code or '').strip().startswith('MT:') else str(code).strip()
    if not CODE.fullmatch(code):
        raise ValueError('Codice Matter non valido: usa il codice di abbinamento di 11 cifre o il testo del QR (MT:…)')
    node = call('commission_with_code', {'code': code, 'network_only': True}, timeout=180)
    return summary(node) if isinstance(node, dict) else {'node_id': node}


def command(node_id, endpoint, name):
    if name not in COMMANDS:
        raise ValueError('Comando Matter: On, Off o Toggle')
    if type(node_id) is not int or type(endpoint) is not int or not 0 <= endpoint <= 65534:
        raise ValueError('Nodo o endpoint Matter non valido')
    cluster, command_name = COMMANDS[name]
    call('device_command', {'node_id': node_id, 'endpoint_id': endpoint, 'cluster_id': cluster, 'command_name': command_name, 'payload': {}})
    return {'node_id': node_id, 'endpoint': endpoint, 'command': name}


def remove(node_id):
    if type(node_id) is not int:
        raise ValueError('Nodo Matter non valido')
    call('remove_node', {'node_id': node_id}, timeout=60)
    return {'removed': node_id}
