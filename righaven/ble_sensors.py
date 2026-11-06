"""Decode what Bluetooth Low Energy sensors broadcast, from the advertisements the launcher heard.

Many cheap sensors (thermometers, hygrometers, door and motion sensors) never connect: they
broadcast readings in their advertisements. The open formats are decoded here:
- BTHome v2 (service data 0xFCD2), used by Shelly BLU and by custom firmwares;
- ATC1441 and pvvx custom formats (service data 0x181A), the custom firmwares of Xiaomi LYWSD03MMC;
- Xiaomi MiBeacon (service data 0xFE95) when not encrypted.
Encrypted payloads are reported as such: decrypting them needs the device's bind key.
"""
import struct

# BTHome v2 objects: id -> (name, size, signed, factor, unit)
BTHOME = {
    0x00: ('packet', 1, False, 1, ''), 0x01: ('battery', 1, False, 1, '%'), 0x02: ('temperature', 2, True, 0.01, '°C'),
    0x03: ('humidity', 2, False, 0.01, '%'), 0x04: ('pressure', 3, False, 0.01, 'hPa'), 0x05: ('illuminance', 3, False, 0.01, 'lx'),
    0x06: ('mass', 2, False, 0.01, 'kg'), 0x08: ('dewpoint', 2, True, 0.01, '°C'), 0x09: ('count', 1, False, 1, ''),
    0x0A: ('energy', 3, False, 0.001, 'kWh'), 0x0B: ('power', 3, False, 0.01, 'W'), 0x0C: ('voltage', 2, False, 0.001, 'V'),
    0x0D: ('pm2_5', 2, False, 1, 'µg/m³'), 0x0E: ('pm10', 2, False, 1, 'µg/m³'), 0x0F: ('generic_boolean', 1, False, 1, ''),
    0x10: ('power_on', 1, False, 1, ''), 0x11: ('opening', 1, False, 1, ''), 0x12: ('co2', 2, False, 1, 'ppm'),
    0x13: ('tvoc', 2, False, 1, 'µg/m³'), 0x14: ('moisture', 2, False, 0.01, '%'), 0x15: ('battery_low', 1, False, 1, ''),
    0x1A: ('door', 1, False, 1, ''), 0x20: ('moisture_detected', 1, False, 1, ''), 0x21: ('motion', 1, False, 1, ''),
    0x2D: ('window', 1, False, 1, ''), 0x2E: ('humidity', 1, False, 1, '%'), 0x2F: ('moisture', 1, False, 1, '%'),
    0x3A: ('button', 1, False, 1, ''), 0x3F: ('rotation', 2, True, 0.1, '°'), 0x40: ('distance', 2, False, 1, 'mm'),
    0x43: ('current', 2, False, 0.001, 'A'), 0x45: ('temperature', 2, True, 0.1, '°C'), 0x46: ('uv_index', 1, False, 0.1, ''),
    0x47: ('volume', 2, False, 0.1, 'L'), 0x4A: ('voltage', 2, False, 0.1, 'V'), 0x51: ('acceleration', 2, False, 0.001, 'm/s²'),
    0x5D: ('current', 2, True, 0.001, 'A'), 0x5E: ('direction', 2, False, 0.01, '°'), 0x5F: ('precipitation', 2, False, 1, 'mm'),
}


def _integer(data, signed):
    return int.from_bytes(data, 'little', signed=signed)


def bthome(payload):
    if not payload:
        return {}
    info = payload[0]
    if info & 0x01:
        return {'encrypted': True}
    if info >> 5 != 2:
        return {}
    readings, position = {}, 1
    while position < len(payload):
        object_id = payload[position]
        spec = BTHOME.get(object_id)
        if spec is None:
            break  # unknown size: the rest cannot be read safely
        name, size, signed, factor, unit = spec
        chunk = payload[position + 1:position + 1 + size]
        if len(chunk) < size:
            break
        value = _integer(chunk, signed) * factor
        value = round(value, 4) if isinstance(value, float) else value
        if name != 'packet':
            readings[name] = {'value': value, 'unit': unit} if unit else value
        position += 1 + size
    return readings


def atc(payload):
    if len(payload) == 13:  # ATC1441: MAC, temperature x10 (BE), humidity %, battery %, battery mV (BE), counter
        temperature, humidity, battery, millivolts = struct.unpack('>hBBH', payload[6:12])
        return {'temperature': {'value': temperature / 10, 'unit': '°C'}, 'humidity': {'value': humidity, 'unit': '%'},
                'battery': {'value': battery, 'unit': '%'}, 'voltage': {'value': millivolts / 1000, 'unit': 'V'}}
    if len(payload) in (15, 16):  # pvvx custom: MAC, temperature x100, humidity x100, battery mV, battery %, counter, flags (LE)
        temperature, humidity, millivolts, battery = struct.unpack('<hHHB', payload[6:13])
        return {'temperature': {'value': temperature / 100, 'unit': '°C'}, 'humidity': {'value': humidity / 100, 'unit': '%'},
                'battery': {'value': battery, 'unit': '%'}, 'voltage': {'value': millivolts / 1000, 'unit': 'V'}}
    return {}


def mibeacon(payload):
    if len(payload) < 5:
        return {}
    control = int.from_bytes(payload[0:2], 'little')
    if control & 0x08:
        return {'encrypted': True}
    position = 5  # frame control, product id, counter
    if control & 0x10:
        position += 6  # MAC
    if control & 0x20:
        position += 1  # capability
    if not control & 0x40 or position + 3 > len(payload):
        return {}
    object_id = int.from_bytes(payload[position:position + 2], 'little')
    size = payload[position + 2]
    data = payload[position + 3:position + 3 + size]
    if len(data) < size:
        return {}
    if object_id == 0x1004 and size == 2:
        return {'temperature': {'value': _integer(data, True) / 10, 'unit': '°C'}}
    if object_id == 0x1006 and size == 2:
        return {'humidity': {'value': _integer(data, False) / 10, 'unit': '%'}}
    if object_id == 0x100A and size >= 1:
        return {'battery': {'value': data[0], 'unit': '%'}}
    if object_id == 0x100D and size == 4:
        return {'temperature': {'value': _integer(data[:2], True) / 10, 'unit': '°C'},
                'humidity': {'value': _integer(data[2:], False) / 10, 'unit': '%'}}
    return {}


DECODERS = {'fcd2': ('BTHome', bthome), '181a': ('ATC/pvvx', atc), 'fe95': ('Xiaomi MiBeacon', mibeacon)}


def _hex(value):
    try:
        return bytes.fromhex(''.join(str(value).split()))
    except ValueError:
        return b''


def uuid16(key):
    """'fcd2', '0xFCD2' or '0000fcd2-0000-1000-8000-00805f9b34fb' -> 'fcd2'."""
    key = str(key).lower().removeprefix('0x')
    if len(key) == 36 and key.endswith('-0000-1000-8000-00805f9b34fb'):
        key = key[4:8]
    return key if len(key) == 4 else ''


def decode(service_data):
    """Readings from the service data of one advertisement ({uuid: hex}), with the format name."""
    for key, value in (service_data or {}).items():
        decoder = DECODERS.get(uuid16(key))
        if decoder:
            readings = decoder[1](_hex(value))
            if readings:
                return {'format': decoder[0], **({'encrypted': True} if readings.get('encrypted') else {'readings': readings})}
    return {}
