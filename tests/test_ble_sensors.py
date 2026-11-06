"""Readings broadcast by Bluetooth LE sensors: BTHome v2, ATC/pvvx, Xiaomi MiBeacon."""
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from righaven import ble_sensors, device_discovery


class BleSensorTests(unittest.TestCase):
    def test_bthome_v2(self):
        result = ble_sensors.decode({'0000fcd2-0000-1000-8000-00805f9b34fb': '40 00 a1 01 64 02 ca 09 03 bf 13'})
        self.assertEqual(result['format'], 'BTHome')
        self.assertEqual(result['readings'], {'battery': {'value': 100, 'unit': '%'}, 'temperature': {'value': 25.06, 'unit': '°C'},
                                              'humidity': {'value': 50.55, 'unit': '%'}})
        self.assertEqual(ble_sensors.decode({'fcd2': '41 02 ca 09'}), {'format': 'BTHome', 'encrypted': True})
        # An unknown object stops decoding instead of misreading the rest.
        self.assertEqual(ble_sensors.decode({'fcd2': '40 01 64 ff 00 02 ca 09'})['readings'], {'battery': {'value': 100, 'unit': '%'}})

    def test_atc_and_pvvx(self):
        atc = ble_sensors.decode({'181a': 'a4c138aabbcc00e7325c0bb81a'})['readings']
        self.assertEqual((atc['temperature']['value'], atc['humidity']['value'], atc['battery']['value']), (23.1, 50, 92))
        payload = bytes.fromhex('ccbbaa38c1a4') + struct.pack('<hHHBBB', -251, 5123, 2950, 80, 7, 4)
        pvvx = ble_sensors.decode({'0x181A': payload.hex()})['readings']
        self.assertEqual((pvvx['temperature']['value'], pvvx['humidity']['value'], pvvx['voltage']['value']), (-2.51, 51.23, 2.95))

    def test_mibeacon_plain_and_encrypted(self):
        plain = '5000' + '5b05' + '01' + 'ccbbaa38c1a4' + '0d1004' + 'e100f401'
        self.assertEqual(ble_sensors.decode({'fe95': plain})['readings'],
                         {'temperature': {'value': 22.5, 'unit': '°C'}, 'humidity': {'value': 50.0, 'unit': '%'}})
        self.assertTrue(ble_sensors.decode({'fe95': '5858' + '5b05' + '01' + 'ccbbaa38c1a4' + 'aabbcc'})['encrypted'])
        self.assertEqual(ble_sensors.decode({'abcd': '00'}), {})
        self.assertEqual(ble_sensors.decode({'fcd2': 'zz'}), {})

    def test_report_and_history_are_decoded_for_the_page_and_csv(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'RIGHAVEN_DISCOVERY_DIR': folder}):
            (Path(folder) / 'bluetooth.json').write_text(json.dumps({'scanned_at': 'x', 'devices': [
                {'name': 'ATC_AABBCC', 'address': 'A4:C1:38:AA:BB:CC', 'kind': 'ble', 'service_data': {'181a': 'a4c138aabbcc00e7325c0bb81a'}}]}))
            (Path(folder) / 'ble-history.jsonl').write_text(
                json.dumps({'at': '2026-11-05T20:00:00Z', 'address': 'A4:C1:38:AA:BB:CC', 'name': 'ATC', 'service_data': {'181a': 'a4c138aabbcc00e7325c0bb81a'}}) + '\nnot json\n')
            report = device_discovery.bluetooth()
            csv = device_discovery.ble_history_csv()
        self.assertEqual(report['devices'][0]['sensor']['readings']['temperature']['value'], 23.1)
        self.assertIn('2026-11-05T20:00:00Z,A4:C1:38:AA:BB:CC,ATC,ATC/pvvx,temperature,23.1,°C', csv)


if __name__ == '__main__':
    unittest.main()
