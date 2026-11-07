"""Vehicle diagnostics (OBD-II) through a Bluetooth LE ELM327 adapter, read only.

Bluetooth LE adapters (the cheap "OBDII" dongles, Vgate, vLinker...) never appear as a COM port:
they take ELM327 commands on one characteristic and answer only by notification on another. The
PC or phone agent does the whole dialog in one connection (ble-exchange) and RigHaven decodes it
here. Only the fixed requests below are sent: they read the vehicle and change nothing in it
(clearing codes, Mode 04, is never sent this way). The ELM327 settings (echo, spaces) reset when
the adapter is unplugged.
"""
import re

# Service, write characteristic, notify characteristic of the common adapters.
KNOWN = (
    ('0000fff0-0000-1000-8000-00805f9b34fb', '0000fff2-0000-1000-8000-00805f9b34fb', '0000fff1-0000-1000-8000-00805f9b34fb'),
    ('0000ffe0-0000-1000-8000-00805f9b34fb', '0000ffe1-0000-1000-8000-00805f9b34fb', '0000ffe1-0000-1000-8000-00805f9b34fb'),
    ('000018f0-0000-1000-8000-00805f9b34fb', '00002af1-0000-1000-8000-00805f9b34fb', '00002af0-0000-1000-8000-00805f9b34fb'),
    ('e7810a71-73ae-499d-8c15-faa9aef0c3f2', 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f', 'bef8d6c9-9c21-4c9e-b632-bd58c1009f9f'),
)
SETUP = ('ATZ', 'ATE0', 'ATL0', 'ATS0', 'ATH0', 'ATSP0')
LIVE = {'010C': 'rpm', '010D': 'speed_kmh', '0105': 'coolant_c', '0104': 'engine_load_pct', '0111': 'throttle_pct',
        '010F': 'intake_air_c', '0142': 'module_voltage_v'}
REQUESTS = {
    'codes': SETUP + ('ATRV', '0100', 'ATDPN', '0101', '03', '07', '0A'),
    'live': SETUP + ('ATRV', '0100', 'ATDPN') + tuple(LIVE),
    'info': SETUP + ('ATI', 'ATRV', '0100', 'ATDPN', '0101', '0902'),
}
# Whatever happens, nothing else reaches the adapter: Mode 04 (clear codes) and any write command stay out.
ALLOWED = set(SETUP) | {'ATI', 'ATRV', 'ATDPN', '0100', '0101', '03', '07', '0A', '0902'} | set(LIVE)
WAIT_MS = 8000  # protocol search on the first request can take several seconds
PROMPT = '3e'   # the ELM327 ">" that ends every answer
ERRORS = ('NO DATA', 'UNABLE TO CONNECT', 'CAN ERROR', 'BUS ERROR', 'BUS INIT: ...ERROR', 'STOPPED', 'ERROR', '?')
NOTE = ('Read only, standard OBD-II: engine and emissions. Manufacturer-specific modules (ABS, airbags, gearbox, body), '
        'common on Chinese cars, are not covered: a lit warning light with no code here belongs to one of those.')
SYSTEMS = {'P': 'powertrain', 'C': 'chassis', 'B': 'body', 'U': 'network'}


def commands(request):
    if request not in REQUESTS:
        raise ValueError('OBD request: codes, live o info')
    return list(REQUESTS[request])


def encode(command):
    if command not in ALLOWED:
        raise ValueError('OBD command not allowed: ' + command)
    return (command + '\r').encode().hex()


def pick(services):
    """Service, write and notify characteristics of an adapter, from ble-inspect."""
    found = {s.get('uuid', '').lower(): {c.get('uuid', '').lower(): c.get('properties') or [] for c in s.get('characteristics') or []}
             for s in services or []}
    for service, write, notify in KNOWN:
        if write in found.get(service, {}) and notify in found.get(service, {}):
            return service, write, notify
    for service, characteristics in found.items():
        writes = [u for u, p in characteristics.items() if {'Write', 'WriteWithoutResponse'} & set(p)]
        notifies = [u for u, p in characteristics.items() if {'Notify', 'Indicate'} & set(p)]
        if writes and notifies and not service.startswith('0000180'):  # skip the standard generic services
            return service, writes[0], notifies[0]
    raise ValueError('This Bluetooth device has no service that takes commands and notifies answers: not an ELM327 adapter')


def text(response_hex):
    try:
        return bytes.fromhex(response_hex or '').decode('ascii', 'replace')
    except ValueError:
        return ''


def lines(answer):
    """The data lines of one answer, without prompt, echo, status lines and spaces."""
    out = []
    for line in re.split(r'[\r\n]+', answer.replace('>', '')):
        line = line.strip()
        if not line or line.upper().startswith(('SEARCHING', 'BUS INIT')) or line.upper() == 'OK':
            continue
        out.append(line)
    return out


def error(answer):
    upper = ' '.join(lines(answer)).upper()
    return next((e for e in ERRORS if upper == e or upper.startswith(e)), '')


def messages(answer):
    """Bytes of each ECU message: single lines, or ISO-TP multi-frame lines (length, then 0:, 1:...)."""
    result, current = [], None
    for line in lines(answer):
        compact = line.replace(' ', '').upper()
        if re.fullmatch(r'[0-9A-F]{3}', compact):
            current = []
            result.append(current)
            continue
        frame = re.fullmatch(r'([0-9A-F]):([0-9A-F]+)', compact)
        if frame and current is not None:
            current.extend(bytes.fromhex(frame.group(2)[:len(frame.group(2)) // 2 * 2]))
            continue
        if re.fullmatch(r'([0-9A-F]{2})+', compact):
            result.append(list(bytes.fromhex(compact)))
            current = None
    return [m for m in result if m]


def dtc(a, b):
    return 'PCBU'[a >> 6] + str((a >> 4) & 3) + format(a & 15, 'X') + format(b, '02X')


def describe(code):
    # SAE generic: P0, P2, P34-P39, C0, B0, U0; the others are the manufacturer's own.
    generic = code[1] == '0' or (code[0] == 'P' and (code[1] == '2' or (code[1] == '3' and code[2] in '456789')))
    return {'code': code, 'system': SYSTEMS[code[0]], 'generic': generic}


def codes(answer, mode, can):
    """Trouble codes from a Mode 03/07/0A answer."""
    reply = mode + 0x40
    found = []
    for message in messages(answer):
        if not message or message[0] != reply:
            continue
        body = message[2:2 + 2 * message[1]] if can and len(message) > 1 else message[1:]
        for i in range(0, len(body) - 1, 2):
            if body[i] or body[i + 1]:
                code = dtc(body[i], body[i + 1])
                if code not in found:
                    found.append(code)
    return [describe(c) for c in found]


def pid(answer, number):
    """The data bytes of a Mode 01 answer for that PID (first ECU that answers)."""
    for message in messages(answer):
        for i in range(len(message) - 1):
            if message[i] == 0x41 and message[i + 1] == number:
                return message[i + 2:]
    return None


def live_value(command, data):
    if not data:
        return None
    a, b = data[0], (data[1] if len(data) > 1 else 0)
    return {'010C': ((a * 256) + b) / 4, '010D': a, '0105': a - 40, '0104': round(a * 100 / 255, 1),
            '0111': round(a * 100 / 255, 1), '010F': a - 40, '0142': ((a * 256) + b) / 1000}[command]


def vin(answer):
    for message in messages(answer):
        if len(message) > 3 and message[0] == 0x49 and message[1] == 0x02:
            value = bytes(b for b in message[2:] if 32 < b < 127).decode('ascii')
            value = value[-17:]
            if len(value) == 17:
                return value
    return ''


def decode(request, sent, responses):
    """What the adapter answered, as vehicle data; the raw answers stay in the result."""
    answers = {command: text(responses[i]) if i < len(responses) else '' for i, command in enumerate(sent)}
    adapter = next((line for line in lines(answers.get('ATZ', '') + '\n' + answers.get('ATI', '')) if 'ELM' in line.upper()), '')
    protocol = ''.join(lines(answers.get('ATDPN', ''))).upper().lstrip('A')
    can = protocol in ('6', '7', '8', '9', 'A', 'B', 'C')
    result = {'adapter': adapter, 'battery_voltage': ''.join(lines(answers.get('ATRV', ''))), 'protocol': protocol,
              'vehicle_answers': bool(messages(answers.get('0100', ''))), 'limits': [NOTE]}
    if not result['vehicle_answers']:
        problem = error(answers.get('0100', '')) or 'no answer'
        result['problem'] = ('The adapter answers but the vehicle does not (' + problem + '): ignition on (engine may stay off), '
                             'adapter firmly in the OBD socket, and no other app connected to it.') if adapter or result['battery_voltage'] else \
            ('The adapter did not answer: unplug and plug it again, close any other app using it (phone), and retry.')
    if '0101' in answers:
        data = pid(answers['0101'], 0x01)
        if data:
            result['mil_on'] = bool(data[0] & 0x80)
            result['stored_code_count'] = data[0] & 0x7F
    if request == 'codes':
        result['stored'] = codes(answers.get('03', ''), 0x03, can)
        result['pending'] = codes(answers.get('07', ''), 0x07, can)
        result['permanent'] = codes(answers.get('0A', ''), 0x0A, can)
    if request == 'live':
        result['values'] = {LIVE[c]: live_value(c, pid(answers.get(c, ''), int(c, 16) & 0xFF)) for c in LIVE}
    if request == 'info':
        result['vin'] = vin(answers.get('0902', ''))
    result['raw'] = {command: ' | '.join(lines(answer))[:300] for command, answer in answers.items()}
    return result
