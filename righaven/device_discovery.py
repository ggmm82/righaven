"""Find devices on the owner's local network, so a device connection does not start from an
unknown IP address.

Only a TCP connection attempt is made to a few well-known IoT ports of each address (and one
HTTP request to the home page of the hosts that answer on HTTP): nothing is written to any
device. The owner starts each search on a network shown beforehand; the portable apps pass
the networks of the PC (RIGHAVEN_LOCAL_NETWORKS), because inside WSL or a container the
local Wi-Fi network is not visible.
"""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import os
import re
import socket
import urllib.request

# Port → what usually answers there.
PORTS = {
    80: 'http', 8080: 'http', 443: 'https', 1883: 'mqtt', 8883: 'mqtt-tls', 502: 'modbus-tcp',
    5555: 'adb', 6053: 'esphome', 6668: 'tuya',
    # TVs, media players, phones and cameras: they answer on their own ports, not on the IoT ones.
    8008: 'cast', 8009: 'cast', 6466: 'androidtv-remote', 8001: 'samsung-tv', 8002: 'samsung-tv', 3000: 'lg-webos', 3001: 'lg-webos',
    7000: 'airplay', 62078: 'apple-device', 554: 'rtsp',
}
MAX_ADDRESSES = 4096
CONNECT_TIMEOUT = 0.6
HTTP_TIMEOUT = 2
SIGNATURES = (  # (pattern in the home page or Server header, kind, label)
    (r'tasmota', 'tasmota', 'Tasmota'),
    (r'openbeken|obk', 'openbeken', 'OpenBeken'),
    (r'esphome', 'esphome', 'ESPHome'),
    (r'shelly', 'shelly', 'Shelly'),
    (r'home assistant', 'home-assistant', 'Home Assistant'),
    (r'wled', 'wled', 'WLED'),
)


def private_allowed():
    return os.getenv('RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS', '').lower() in ('1', 'allow', 'true')


def network(value):
    try:
        net = ipaddress.ip_network(str(value).strip(), strict=False)
    except ValueError:
        raise ValueError('Rete non valida: scrivila come 192.168.1.0/24') from None
    if net.version != 4 or not net.is_private or net.is_loopback or net.is_link_local:
        raise ValueError('Si possono cercare dispositivi solo in una rete locale privata (per esempio 192.168.1.0/24)')
    if net.num_addresses > MAX_ADDRESSES:
        raise ValueError('Rete troppo grande: al massimo 4096 indirizzi (per esempio una /20)')
    return net


def local_networks():
    """Networks of the PC given by the launcher, private and searchable."""
    found = []
    for value in os.getenv('RIGHAVEN_LOCAL_NETWORKS', '').split(','):
        try:
            found.append(str(network(value)))
        except ValueError:
            continue
    return list(dict.fromkeys(found))


def _open(address, port):
    """'open', 'refused' (the host is there, the port is closed) or None (no answer)."""
    try:
        with socket.create_connection((address, port), timeout=CONNECT_TIMEOUT):
            return 'open'
    except ConnectionRefusedError:
        return 'refused'
    except OSError:
        return None


def _home_page(address, port):
    request = urllib.request.Request(f'http://{address}:{port}/', headers={'User-Agent': 'RigHaven device discovery'})
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=HTTP_TIMEOUT) as response:
            return (response.headers.get('Server') or '') + ' ' + response.read(8192).decode('utf-8', 'replace')
    except Exception as error:  # Any answer, including an error page, may name the firmware.
        body = getattr(error, 'read', None)
        try:
            return body(4096).decode('utf-8', 'replace') if body else ''
        except Exception:
            return ''


PRESENT = {'kind': 'present', 'label': 'Dispositivo presente, nessun servizio noto aperto',
           'note': 'Risponde ma non offre nessuno dei servizi cercati: spesso un telefono, un PC o una TV in standby. «Ascolta la rete» può dirti cos’è.',
           'suggestion': {'protocol': 'tcp', 'port': 80}}
TV_NOTE = ('Per comandarla da RigHaven e installarle app o pacchetti di aggiornamento ufficiali: Impostazioni → Info → premi 7 volte '
           'su «Build» per le Opzioni sviluppatore, attiva il debug ADB (di rete), poi crea la connessione con protocollo ADB.')


def identify(address, ports, page=''):
    """Kind, label and the connection to suggest for one host."""
    text = page.lower()
    title = re.search(r'<title[^>]*>([^<]{1,80})</title>', page, re.I)
    for pattern, kind, label in SIGNATURES:
        if re.search(pattern, text):
            port = 80 if 80 in ports else 8080
            return {'kind': kind, 'label': label, 'suggestion': {'protocol': 'http', 'port': port}}
    if 6668 in ports:
        return {'kind': 'tuya', 'label': 'Tuya / Smart Life',
                'note': 'Protocollo locale Tuya: crea la connessione con ID dispositivo e local key (dal tuo account Tuya/Smart Life).',
                'suggestion': {'protocol': 'tuya', 'port': 6668}}
    if 5555 in ports:
        return {'kind': 'android', 'label': 'Android / Android TV (debug ADB)', 'suggestion': {'protocol': 'adb', 'port': 5555}}
    if {8008, 8009, 6466} & set(ports):
        return {'kind': 'android-tv', 'label': 'Android TV / Google TV / Chromecast', 'note': TV_NOTE, 'suggestion': {'protocol': 'adb', 'port': 5555}}
    if {8001, 8002} & set(ports):
        return {'kind': 'samsung-tv', 'label': 'Smart TV Samsung (Tizen)', 'note': 'Si comanda dalla rete locale (porta 8001/8002, la TV chiede di autorizzare RigHaven); il firmware si aggiorna solo dal menu della TV o da chiavetta USB.',
                'suggestion': {'protocol': 'http', 'port': 8001}}
    if {3000, 3001} & set(ports):
        return {'kind': 'lg-tv', 'label': 'Smart TV LG (webOS)', 'note': 'Si comanda dalla rete locale (porta 3000/3001, la TV chiede di autorizzare RigHaven); il firmware si aggiorna solo dal menu della TV o da chiavetta USB.',
                'suggestion': {'protocol': 'http', 'port': 3000}}
    if 62078 in ports:
        return {'kind': 'apple', 'label': 'iPhone / iPad', 'note': 'Apple non permette di comandarlo dalla rete.', 'suggestion': {'protocol': 'tcp', 'port': 62078}}
    if 7000 in ports:
        return {'kind': 'airplay', 'label': 'Apple TV / dispositivo AirPlay', 'suggestion': {'protocol': 'http', 'port': 7000}}
    if 554 in ports:
        return {'kind': 'camera', 'label': 'Telecamera (RTSP)', 'suggestion': {'protocol': 'tcp', 'port': 554}}
    if 6053 in ports:
        return {'kind': 'esphome', 'label': 'ESPHome', 'suggestion': {'protocol': 'tcp', 'port': 6053}}
    if 1883 in ports or 8883 in ports:
        return {'kind': 'mqtt', 'label': 'Broker MQTT', 'suggestion': {'protocol': 'mqtt', 'port': 1883 if 1883 in ports else 8883}}
    if 502 in ports:
        return {'kind': 'modbus', 'label': 'Modbus TCP', 'suggestion': {'protocol': 'modbus-tcp', 'port': 502}}
    if 80 in ports or 8080 in ports:
        name = title.group(1).strip() if title else 'Dispositivo con pagina web'
        return {'kind': 'web', 'label': name, 'suggestion': {'protocol': 'http', 'port': 80 if 80 in ports else 8080}}
    return {'kind': 'other', 'label': 'Dispositivo in rete', 'suggestion': {'protocol': 'tcp', 'port': min(ports)}}


def scan(value):
    """Hosts of a private network that answer on the IoT ports, identified when possible."""
    if not private_allowed():
        raise ValueError('Le reti private non sono consentite: l’amministratore può abilitarle con RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS=allow')
    net = network(value)
    hosts = [str(a) for a in (net.hosts() if net.num_addresses > 2 else net)]
    pairs = [(address, port) for address in hosts for port in PORTS]
    with ThreadPoolExecutor(max_workers=128) as pool:
        answers = list(pool.map(lambda pair: _open(*pair), pairs))
    found, present = {}, set()
    for (address, port), answer in zip(pairs, answers):
        if answer == 'open':
            found.setdefault(address, []).append(port)
        elif answer == 'refused':
            present.add(address)
    for address in present - set(found):
        found[address] = []  # it answered "closed": a phone, a PC or a TV without the usual services
    def describe(item):
        address, ports = item
        web = next((p for p in (80, 8080) if p in ports), None)
        page = _home_page(address, web) if web else ''
        try:
            name = socket.gethostbyaddr(address)[0]
        except OSError:
            name = ''
        title = re.search(r'<title[^>]*>\s*([^<]{1,120})', page, re.I)
        return {'address': address, 'ports': sorted(ports), 'name': name, 'title': title.group(1).strip() if title else '',
                **(identify(address, ports, page) if ports else PRESENT)}
    with ThreadPoolExecutor(max_workers=16) as pool:
        devices = list(pool.map(describe, found.items()))
    devices.sort(key=lambda d: ipaddress.ip_address(d['address']))
    return {'network': str(net), 'ports': sorted(PORTS), 'devices': devices}


def _identified(devices):
    """Hosts found by an agent in the home network: the same identification as a search from this server."""
    found = []
    for item in devices or []:
        if not isinstance(item, dict):
            continue
        try:
            address = str(ipaddress.ip_address(str(item.get('address'))))
        except ValueError:
            continue
        ports = sorted(p for p in (item.get('ports') or []) if type(p) is int and p in PORTS)
        page = str(item.get('page') or '')[:12000]
        title = re.search(r'<title[^>]*>\s*([^<]{1,120})', page, re.I)
        found.append({'address': address, 'ports': ports, 'name': str(item.get('name') or '')[:120],
                      'title': title.group(1).strip() if title else '', **(identify(address, ports, page) if ports else PRESENT)})
    found.sort(key=lambda d: ipaddress.ip_address(d['address']))
    return found


def identified(devices):
    return _identified(devices)


def scan_from_agent(agent, value):
    """The same search, run by the agent in its own network (this server cannot reach a home network)."""
    from . import host_bridge
    net = network(value)
    answer = host_bridge.run('net-scan', {'network': str(net)}, timeout=600, agent=agent)
    return {'network': str(net), 'ports': sorted(PORTS), 'devices': _identified(answer.get('devices'))}


def explore_from_agent(agent, address):
    try:
        host = ipaddress.ip_address(str(address).strip())
    except ValueError as error:
        raise ValueError('Indirizzo non valido: ' + str(address)[:60]) from error
    devices = scan_from_agent(agent, str(host) + '/32')['devices']
    return devices[0] if devices else {'address': str(host), 'ports': [], 'name': '', 'title': '', 'kind': '', 'label': ''}


def explore(address):
    """One address the owner chose: which IoT ports answer, its name and home page. Nothing is written."""
    try:
        host = ipaddress.ip_address(str(address).strip())
    except ValueError as error:
        raise ValueError('Indirizzo non valido: ' + str(address)[:60]) from error
    devices = scan(str(host) + ('/32' if host.version == 4 else '/128'))['devices']
    return devices[0] if devices else {'address': str(host), 'ports': [], 'name': '', 'title': '', 'kind': '', 'label': ''}


DISCOVERY_DIR = '/run/righaven/discovery'


def _reports(directory=None):
    """The launcher's discovery folder, or the folder of one agent's reports."""
    from pathlib import Path
    return Path(directory) if directory else Path(os.getenv('RIGHAVEN_DISCOVERY_DIR', DISCOVERY_DIR))


def capture_file(directory=None):
    """The last traffic recording handed over by the launcher."""
    from pathlib import Path
    path = _reports(directory) / 'capture.pcapng'
    if not path.is_file() or path.is_symlink():
        raise ValueError('Nessuna registrazione del traffico: premi «Registra il traffico»')
    return str(path)
BLUETOOTH_HINTS = (  # (words in the name, hint)
    (('obd', 'elm327', 'v-link', 'vgate'), 'obd'),
    (('tuya', 'smart life'), 'tuya'),
    (('esp32', 'esp-', 'esphome'), 'esp32'),
    (('lywsd', 'xiaomi', 'mj_'), 'xiaomi'),
    (('shelly',), 'shelly'),
    (('tv', 'bravia', 'android'), 'tv'),
)


# Bluetooth company identifiers (manufacturer data): who made a device that sends no name.
COMPANIES = {
    '004c': ('Apple', 'iPhone, iPad, Mac, AirPods, Apple Watch o AirTag'), '0075': ('Samsung', 'telefono, Galaxy Buds, Galaxy Watch o SmartTag'),
    '00e0': ('Google', 'telefono Android (Fast Pair) o dispositivo Google'), '0006': ('Microsoft', 'PC Windows (Swift Pair) o accessorio Microsoft'),
    '038f': ('Xiaomi', 'dispositivo Xiaomi'), '027d': ('Huawei', 'telefono, cuffie o orologio Huawei'), '012d': ('Sony', 'cuffie o dispositivo Sony'),
    '0157': ('Huami / Amazfit', 'smartwatch o fitness band'), '0171': ('Amazon', 'Echo, Fire TV o altro dispositivo Amazon'),
    '0087': ('Garmin', 'orologio o dispositivo Garmin'), '0059': ('Nordic Semiconductor', 'modulo BLE (sensori, schede di sviluppo)'),
    '02e5': ('Espressif', 'scheda ESP32 con Bluetooth'), '07d0': ('Tuya', 'dispositivo Tuya / Smart Life'), '0499': ('Ruuvi', 'sensore Ruuvi'),
    '0131': ('Cypress / Infineon', 'modulo BLE'), '000f': ('Broadcom', 'chip Bluetooth Broadcom'), '0002': ('Intel', 'PC con Bluetooth Intel'),
    '001d': ('Qualcomm', 'cuffie o dispositivo con chip Qualcomm'), '0310': ('SGL Italia', 'dispositivo SGL'), '0822': ('Adafruit', 'scheda Adafruit'),
}


def bluetooth_hint(name):
    text = (name or '').lower()
    if text.startswith('ty'):
        return 'tuya'
    for words, hint in BLUETOOTH_HINTS:
        if any(word in text for word in words):
            return hint
    return ''


def serial_ports(directory=None):
    """Windows COM ports shared by RigHaven.exe serial while RigHaven runs (host and TCP port)."""
    import json
    from pathlib import Path
    path = _reports(directory) / 'serial.json'
    try:
        report = json.loads(path.read_text()[:262_144])
    except (OSError, ValueError):
        return []
    ports = []
    for item in (report.get('ports') or []) if isinstance(report, dict) else []:
        if not isinstance(item, dict) or not re.fullmatch(r'COM[0-9]{1,3}', str(item.get('name'))):
            continue
        try:
            host = str(ipaddress.ip_address(str(item.get('host'))))
        except ValueError:
            continue
        port = item.get('port')
        if type(port) is int and 41000 <= port <= 41999:
            ports.append({'name': item['name'], 'label': str(item.get('label') or '')[:120], 'host': host, 'port': port,
                          'hint': bluetooth_hint(str(item.get('label') or '')) or ('bluetooth' if 'bluetooth' in str(item.get('label')).lower() else '')})
    return ports


def ble_history_csv(directory=None):
    """Readings of Bluetooth LE sensors heard by the launcher over time, one row per reading."""
    import csv
    import io
    import json
    from pathlib import Path
    from .ble_sensors import decode
    path = _reports(directory) / 'ble-history.jsonl'
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['at', 'address', 'name', 'format', 'quantity', 'value', 'unit'])
    try:
        lines = path.read_text(errors='replace').splitlines()[-50000:]
    except OSError:
        lines = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict) or not isinstance(item.get('service_data'), dict):
            continue
        sensor = decode(item['service_data'])
        for quantity, reading in (sensor.get('readings') or {}).items():
            value, unit = (reading.get('value'), reading.get('unit', '')) if isinstance(reading, dict) else (reading, '')
            writer.writerow([str(item.get('at', ''))[:40], str(item.get('address', ''))[:40], str(item.get('name', ''))[:120],
                             sensor['format'], quantity, value, unit])
    return out.getvalue()


def bluetooth(directory=None):
    """The last Bluetooth search made by the launcher on the PC (RigHaven.exe bluetooth)."""
    import json
    from pathlib import Path
    path = _reports(directory) / 'bluetooth.json'
    try:
        report = json.loads(path.read_text()[:1_048_576])
    except (OSError, ValueError):
        return None
    devices = []
    for item in report.get('devices') or [] if isinstance(report, dict) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '')[:120]
        device = {'name': name, 'address': str(item.get('address') or '')[:40], 'port': str(item.get('port') or '')[:12],
                  'kind': str(item.get('kind') or 'bluetooth')[:12], 'paired': item.get('paired') is True,
                  'present': item.get('present') is not False, 'connected': item.get('connected') is True,
                  **({'maker': COMPANIES[str(item.get('company')).lower()][0], 'maker_hint': COMPANIES[str(item.get('company')).lower()][1]}
                     if str(item.get('company') or '').lower() in COMPANIES else {}),
                  'hint': item.get('hint') if item.get('hint') in {h for _, h in BLUETOOTH_HINTS} else bluetooth_hint(name)}
        if isinstance(item.get('service_data'), dict):
            from .ble_sensors import decode
            device['sensor'] = decode({str(k)[:40]: str(v)[:512] for k, v in list(item['service_data'].items())[:8]})
        devices.append(device)
    warnings = [str(w)[:300] for w in (report.get('warnings') or [])[:4] if isinstance(w, str)] if isinstance(report, dict) else []
    return {'scanned_at': str(report.get('scanned_at') or '')[:40], 'devices': devices[:200], 'warnings': warnings}


WIFI_HINTS = (  # (lowercase SSID prefixes or words, hint)
    (('smartlife', 'smart life', 'sl-', 'tuya'), 'tuya'),
    (('tasmota',), 'tasmota'),
    (('shelly',), 'shelly'),
    (('openbeken', 'openbk', 'obk'), 'openbeken'),
    (('wled',), 'wled'),
    (('esp_', 'esp-', 'esphome', 'fallback hotspot'), 'esp'),
    (('daikinap', 'daikin'), 'daikin'),
    (('[lg_', 'lg_', 'lge_'), 'lg'),
    (('direct-',), 'direct'),
)


def wifi_hint(ssid):
    text = (ssid or '').lower()
    for words, hint in WIFI_HINTS:
        if any(text.startswith(word) or (len(word) > 4 and word in text) for word in words):
            return hint
    return ''


def wifi(directory=None):
    """The last Wi-Fi scan of the PC (launcher): nearby networks, including the setup networks
    of devices not configured yet."""
    import json
    from pathlib import Path
    path = _reports(directory) / 'wifi.json'
    try:
        report = json.loads(path.read_text()[:1_048_576])
    except (OSError, ValueError):
        return None
    networks = []
    for item in (report.get('networks') or []) if isinstance(report, dict) else []:
        if not isinstance(item, dict):
            continue
        ssid = str(item.get('ssid') or '')[:64]
        signal = item.get('signal')
        networks.append({'ssid': ssid, 'bssid': str(item.get('bssid') or '')[:17], 'open': item.get('open') is True,
                         'signal': signal if type(signal) is int and 0 <= signal <= 100 else None, 'hint': wifi_hint(ssid)})
    networks.sort(key=lambda n: (n['hint'] == '', -(n['signal'] or 0)))
    return {'scanned_at': str(report.get('scanned_at') or '')[:40], 'networks': networks[:200]}
