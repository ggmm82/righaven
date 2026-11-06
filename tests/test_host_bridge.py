"""Actions on the PC asked from the page and carried out by the launcher."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from righaven import host_bridge


class HostBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        patcher = patch.dict(os.environ, {'RIGHAVEN_HOST_DIR': self.temp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def heartbeat(self, age=0, actions=('bluetooth-scan', 'usb-attach', 'com-share', 'evil')):
        (self.base / 'heartbeat.json').write_text(json.dumps({'at': time.time() - age, 'platform': 'windows', 'actions': list(actions), 'matter': False}))

    def test_requests_need_a_launcher_that_answers_and_offers_the_action(self):
        with self.assertRaisesRegex(ValueError, 'non risponde'):
            host_bridge.request('bluetooth-scan')
        self.heartbeat(age=60)
        self.assertFalse(host_bridge.state()['connected'])
        self.heartbeat()
        self.assertEqual(host_bridge.state()['actions'], ['bluetooth-scan', 'usb-attach', 'com-share'])
        with self.assertRaisesRegex(ValueError, 'non è disponibile'):
            host_bridge.request('matter-enable')
        with self.assertRaisesRegex(ValueError, 'non disponibile'):
            host_bridge.request('format-disk')

    def test_arguments_are_validated_and_results_followed(self):
        self.heartbeat()
        for bad in ({'busid': '1-4; rm'}, {}):
            with self.assertRaises(ValueError):
                host_bridge.request('usb-attach', bad)
        with self.assertRaises(ValueError):
            host_bridge.request('com-share', {'name': 'COM5 && x'})
        queued = host_bridge.request('usb-attach', {'busid': '1-4', 'extra': 'ignored'})
        written = json.loads((self.base / 'requests' / (queued['id'] + '.json')).read_text())
        self.assertEqual((written['action'], written['args']), ('usb-attach', {'busid': '1-4'}))
        self.assertEqual(host_bridge.result(queued['id'])['status'], 'queued')
        (self.base / 'results').mkdir()
        (self.base / 'results' / (queued['id'] + '.json')).write_text(json.dumps({'ok': True, 'ports': ['/dev/ttyUSB0']}))
        self.assertEqual(host_bridge.result(queued['id']), {'id': queued['id'], 'status': 'done', 'result': {'ok': True, 'ports': ['/dev/ttyUSB0']}})
        (self.base / 'results' / (queued['id'] + '.json')).write_text(json.dumps({'error': 'busy'}))
        self.assertEqual(host_bridge.result(queued['id'])['status'], 'failed')
        with self.assertRaises(ValueError):
            host_bridge.result('../../etc/passwd')


    def test_bluetooth_le_arguments_are_normalised_and_checked(self):
        self.heartbeat(actions=('ble-read', 'ble-write'))
        job = host_bridge.request('ble-read', {'address': '38-a5-c9-3c-2e-9f', 'service': '0x180A', 'characteristic': '2a29'})
        sent = json.loads((self.base / 'requests' / (job['id'] + '.json')).read_text())['args']
        self.assertEqual(sent, {'address': '38:A5:C9:3C:2E:9F', 'service': '0000180a-0000-1000-8000-00805f9b34fb',
                                'characteristic': '00002a29-0000-1000-8000-00805f9b34fb'})
        for args in ({'address': 'nope', 'service': '180a', 'characteristic': '2a29'},
                     {'address': '38:A5:C9:3C:2E:9F', 'service': '180a', 'characteristic': '2a29', 'value': 'xyz'}):
            with self.assertRaises(ValueError):
                host_bridge.request('ble-write', args)
        self.assertIn('ble-write', host_bridge.APPROVED_ONLY)

    def test_home_wifi_password_goes_only_to_the_launcher_request(self):
        self.heartbeat(actions=('wifi-provision',))
        job = host_bridge.request('wifi-provision', {'ssid': 'tasmota-1A2B', 'hint': 'tasmota', 'password': ' con spazi ', 'home': ''})
        sent = json.loads((self.base / 'requests' / (job['id'] + '.json')).read_text())['args']
        self.assertEqual(sent, {'ssid': 'tasmota-1A2B', 'hint': 'tasmota', 'password': ' con spazi '})
        for args in ({'ssid': 'x', 'hint': 'evil', 'password': '12345678'}, {'ssid': 'x', 'hint': 'esp', 'password': 'short'},
                     {'ssid': 'a\nb', 'hint': 'esp', 'password': '12345678'}):
            with self.assertRaises(ValueError):
                host_bridge.request('wifi-provision', args)

    def test_traffic_recording_is_bounded(self):
        self.heartbeat(actions=('traffic-capture', 'net-listen'))
        host_bridge.request('traffic-capture', {'seconds': '60'})
        host_bridge.request('net-listen')
        host_bridge.request('traffic-capture', {'seconds': '1800'})
        for seconds in ('9', '1801', '9999', 'x'):
            with self.assertRaises(ValueError):
                host_bridge.request('traffic-capture', {'seconds': seconds})

if __name__ == '__main__':
    unittest.main()
