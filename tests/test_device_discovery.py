"""Find devices on the owner's network and the Bluetooth devices seen by the PC."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import device_discovery as discovery


class DeviceDiscoveryTests(unittest.TestCase):
    def test_only_small_private_networks_can_be_searched(self):
        self.assertEqual(str(discovery.network('192.168.1.37/24')), '192.168.1.0/24')
        for bad in ('8.8.8.0/24', '127.0.0.0/24', '10.0.0.0/8', 'casa', '169.254.0.0/24', 'fd00::/64'):
            with self.assertRaises(ValueError):
                discovery.network(bad)
        with patch.dict(os.environ, {'RIGHAVEN_LOCAL_NETWORKS': '192.168.1.0/24,8.8.8.0/24,bad,192.168.1.0/24'}):
            self.assertEqual(discovery.local_networks(), ['192.168.1.0/24'])

    def test_search_needs_private_networks_allowed(self):
        with patch.dict(os.environ, {'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': ''}):
            with self.assertRaisesRegex(ValueError, 'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS'):
                discovery.scan('192.168.1.0/24')

    def test_hosts_are_identified_and_a_connection_is_suggested(self):
        answers = {('192.168.1.10', 6668), ('192.168.1.20', 80), ('192.168.1.30', 5555), ('192.168.1.40', 1883), ('192.168.1.50', 80),
                   ('192.168.1.60', 8009), ('192.168.1.60', 6466), ('192.168.1.70', 8002)}
        refused = {'192.168.1.80'}  # a phone: it answers "closed" on every port
        pages = {'192.168.1.20': '<html><title>Tasmota</title></html>', '192.168.1.50': '<title>Router</title>'}
        with patch.dict(os.environ, {'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'}), \
             patch.object(discovery, '_open', side_effect=lambda a, p: 'open' if (a, p) in answers else 'refused' if a in refused else None), \
             patch.object(discovery, '_home_page', side_effect=lambda a, p: pages.get(a, '')), \
             patch.object(discovery.socket, 'gethostbyaddr', side_effect=OSError):
            result = discovery.scan('192.168.1.0/24')
        found = {d['address']: d for d in result['devices']}
        self.assertEqual(list(found), ['192.168.1.10', '192.168.1.20', '192.168.1.30', '192.168.1.40', '192.168.1.50', '192.168.1.60', '192.168.1.70', '192.168.1.80'])
        self.assertEqual((found['192.168.1.60']['kind'], found['192.168.1.60']['suggestion']['protocol']), ('android-tv', 'adb'))
        self.assertIn('ADB', found['192.168.1.60']['note'])
        self.assertEqual(found['192.168.1.70']['kind'], 'samsung-tv')
        self.assertEqual((found['192.168.1.80']['kind'], found['192.168.1.80']['ports']), ('present', []))
        self.assertEqual((found['192.168.1.10']['kind'], found['192.168.1.10']['suggestion']), ('tuya', {'protocol': 'tuya', 'port': 6668}))
        self.assertEqual(found['192.168.1.20']['label'], 'Tasmota')
        self.assertEqual(found['192.168.1.30']['suggestion']['protocol'], 'adb')
        self.assertEqual(found['192.168.1.40']['suggestion'], {'protocol': 'mqtt', 'port': 1883})
        self.assertEqual(found['192.168.1.50']['label'], 'Router')

    def test_one_address_is_explored_on_its_own(self):
        with patch.object(discovery, 'scan', return_value={'devices': [{'address': '192.168.1.44', 'ports': [6668]}]}) as scan:
            self.assertEqual(discovery.explore(' 192.168.1.44 ')['ports'], [6668])
        scan.assert_called_once_with('192.168.1.44/32')
        with patch.object(discovery, 'scan', return_value={'devices': []}):
            self.assertEqual(discovery.explore('192.168.1.45')['ports'], [])
        with self.assertRaises(ValueError):
            discovery.explore('evil.example.com')

    def test_bluetooth_report_of_the_launcher_is_read_safely(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'RIGHAVEN_DISCOVERY_DIR': folder}):
            self.assertIsNone(discovery.bluetooth())
            (Path(folder) / 'bluetooth.json').write_text(json.dumps({'scanned_at': '2026-11-05T20:00:00Z', 'devices': [
                {'name': 'OBDII', 'address': '00:1D:A5:68:98:8B', 'kind': 'classic', 'paired': True},
                {'name': 'TY', 'address': 'DC:23', 'kind': 'ble', 'paired': 'yes', 'hint': '<script>'}, 'junk',
                {'name': '', 'address': '4A:00:11:22:33:44', 'kind': 'ble', 'company': '004C'}],
                'warnings': ['readings: listener not built', {'x': 1}]}))
            report = discovery.bluetooth()
        self.assertEqual(report['warnings'], ['readings: listener not built'])
        self.assertEqual([d['hint'] for d in report['devices']], ['obd', 'tuya', ''])
        self.assertFalse(report['devices'][1]['paired'])
        self.assertEqual(report['devices'][2]['maker'], 'Apple')
        self.assertNotIn('maker', report['devices'][0])

    def test_shared_com_ports_are_offered_as_raw_tcp_serial_connections(self):
        from righaven import connections
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'RIGHAVEN_DISCOVERY_DIR': folder}):
            (Path(folder) / 'serial.json').write_text(json.dumps({'ports': [
                {'name': 'COM5', 'label': 'OBDII (COM5)', 'host': '172.18.0.1', 'port': 41005},
                {'name': 'COM6;x', 'host': '172.18.0.1', 'port': 41006}, {'name': 'COM7', 'host': 'evil', 'port': 41007},
                {'name': 'COM8', 'host': '172.18.0.1', 'port': 22}]}))
            ports = discovery.serial_ports()
        self.assertEqual([(p['name'], p['hint']) for p in ports], [('COM5', 'obd')])
        with patch.dict(os.environ, {'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'}):
            record = connections.validate({'kind': 'device', 'id': 'obd', 'name': 'OBD', 'transport': 'serial', 'protocol': 'socket',
                                           'host': '172.18.0.1', 'port': 41005, 'baud': 38400})
            legacy = connections.validate({'kind': 'device', 'id': 'pi', 'name': 'Pi', 'transport': 'serial', 'host': 'pi.local', 'port': 4000})
        self.assertEqual(connections.device_file(record)['url'], 'socket://172.18.0.1:41005')
        self.assertEqual(connections.device_file(legacy)['url'], 'rfc2217://pi.local:4000')

    def test_wifi_setup_networks_of_devices_are_recognized(self):
        self.assertEqual([discovery.wifi_hint(n) for n in ('DaikinAP72288', '[LG_Wall-Mount A/C]e3b0', 'WINDTRE-071570')], ['daikin', 'lg', ''])
        self.assertEqual([discovery.wifi_hint(x) for x in ('SmartLife-1A2B', 'tasmota-8F2A1C', 'shellyplus1-abc', 'ESP_12AB', 'DIRECT-xy-HP', 'CasaRossi', 'WLED-AP')],
                         ['tuya', 'tasmota', 'shelly', 'esp', 'direct', '', 'wled'])
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'RIGHAVEN_DISCOVERY_DIR': folder}):
            self.assertIsNone(discovery.wifi())
            (Path(folder) / 'wifi.json').write_text(json.dumps({'scanned_at': 'x', 'networks': [
                {'ssid': 'CasaRossi', 'signal': 95}, {'ssid': 'SmartLife-1A2B', 'signal': 40, 'open': True}, {'ssid': 'x', 'signal': 900}, 'junk']}))
            report = discovery.wifi()
        self.assertEqual([n['ssid'] for n in report['networks']], ['SmartLife-1A2B', 'CasaRossi', 'x'])
        self.assertEqual((report['networks'][0]['hint'], report['networks'][0]['open'], report['networks'][2]['signal']), ('tuya', True, None))


if __name__ == '__main__':
    unittest.main()
