"""The chat finds devices near the PC: home network, nearby Wi-Fi and Bluetooth through the launcher."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    from righaven import tools
except ImportError:  # gateway dependencies
    tools = None


@unittest.skipUnless(tools, 'Gateway dependency environment required')
class FindDevicesToolTests(unittest.TestCase):
    def test_network_wifi_and_bluetooth_are_searched_and_reported(self):
        from righaven import device_discovery
        with tempfile.TemporaryDirectory() as host, tempfile.TemporaryDirectory() as reports, patch.dict(os.environ, {
                'RIGHAVEN_HOST_DIR': host, 'RIGHAVEN_DISCOVERY_DIR': reports, 'RIGHAVEN_LOCAL_NETWORKS': '192.168.1.0/24',
                'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'}):
            (Path(host) / 'heartbeat.json').write_text(json.dumps({'at': time.time(), 'platform': 'windows', 'actions': ['wifi-scan', 'bluetooth-scan']}))
            (Path(reports) / 'wifi.json').write_text(json.dumps({'scanned_at': 'x', 'networks': [{'ssid': 'SmartLife-1A2B', 'signal': 60, 'open': True}]}))
            def answer(identifier):
                (Path(host) / 'results').mkdir(exist_ok=True)
                (Path(host) / 'results' / (identifier + '.json')).write_text('{"ok": true}')
                return {'id': identifier, 'status': 'done', 'result': {'ok': True}}
            with patch.object(device_discovery, 'scan', return_value={'network': '192.168.1.0/24', 'devices': [{'address': '192.168.1.44', 'kind': 'tuya'}]}) as scan, \
                 patch('righaven.host_bridge.result', side_effect=answer), patch('time.sleep'):
                value = json.loads(tools.harness_find_devices.func(runtime=None, where='all'))
        scan.assert_called_once_with('192.168.1.0/24')
        self.assertEqual(value['found']['network']['devices'][0]['kind'], 'tuya')
        self.assertEqual(value['found']['wifi']['networks'][0]['hint'], 'tuya')
        self.assertIsNone(value['found']['bluetooth'])
        with self.assertRaises(ValueError):
            tools.harness_find_devices.func(runtime=None, where='everything')


@unittest.skipUnless(tools, 'Gateway dependency environment required')
class SetupDeviceToolTests(unittest.TestCase):
    def setUp(self):
        from cryptography.fernet import Fernet
        from righaven import connections
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.host, self.reports = base / 'host', base / 'discovery'
        self.reports.mkdir()
        store = base / 'connections'
        for p in (patch.object(connections, 'folder', side_effect=lambda user: store.mkdir(exist_ok=True) or store),
                  patch.dict(os.environ, {'RIGHAVEN_CREDENTIALS_KEY': Fernet.generate_key().decode(), 'RIGHAVEN_HOST_DIR': str(self.host),
                                          'RIGHAVEN_DISCOVERY_DIR': str(self.reports), 'RIGHAVEN_DEVICES': ''}),
                  patch('righaven.tools.resolve_runtime_user_id', return_value='alice'), patch('time.sleep')):
            p.start(); self.addCleanup(p.stop)
        self.host.mkdir()
        (self.host / 'heartbeat.json').write_text(json.dumps({'at': time.time(), 'platform': 'windows',
                                                              'actions': ['usb-list', 'usb-attach', 'com-list', 'com-share']}))

    def answering(self, result, before=None):
        def answer(identifier):
            if before:
                before()
            return {'id': identifier, 'status': 'done', 'result': result}
        return patch('righaven.host_bridge.result', side_effect=answer)

    def test_usb_peripheral_is_attached_and_connected_read_only(self):
        offer = lambda: (self.reports / 'devices.json').write_text('{"devices":"/dev/ttyUSB0"}')
        with self.answering({'ok': True, 'ports': ['/dev/ttyUSB0']}, offer):
            value = json.loads(tools.harness_setup_device.func(runtime=None, kind='usb', target='2-3', name='Telecomando IR'))
        request = json.loads(next((self.host / 'requests').glob('*.json')).read_text())
        self.assertEqual((request['action'], request['args']), ('usb-attach', {'busid': '2-3'}))
        self.assertEqual(value['connection']['id'], 'telecomando-ir')
        self.assertEqual(value['connection']['device'], '/dev/ttyUSB0')
        from righaven import connections
        self.assertFalse(connections.listing('alice')[0]['write_enabled'])
        with self.answering({'ok': True, 'ports': ['/dev/ttyUSB0']}, offer):
            again = json.loads(tools.harness_setup_device.func(runtime=None, kind='usb', target='2-3', name='Telecomando IR'))
        self.assertEqual(again['connection']['id'], 'telecomando-ir-2', 'a free ID is chosen')

    def test_usb_without_serial_port_creates_nothing(self):
        with self.answering({'ok': True, 'ports': []}):
            value = json.loads(tools.harness_setup_device.func(runtime=None, kind='usb', target='2-3'))
        self.assertIsNone(value['connection'])

    def test_com_port_is_shared_and_connected(self):
        share = lambda: (self.reports / 'serial.json').write_text(json.dumps({'ports': [{'name': 'COM5', 'label': 'OBDII', 'host': '172.30.42.1', 'port': 41005}]}))
        with self.answering({'ok': True}, share):
            value = json.loads(tools.harness_setup_device.func(runtime=None, kind='com', target='COM5'))
        self.assertEqual((value['connection']['host'], value['connection']['port'], value['connection']['protocol']), ('172.30.42.1', 41005, 'socket'))

    def test_tuya_keys_are_never_asked_in_chat_and_bad_input_is_refused(self):
        value = json.loads(tools.harness_setup_device.func(runtime=None, kind='network', target='192.168.1.44', protocol='tuya'))
        self.assertIsNone(value['connection'])
        self.assertIn('never ask', value['instruction'])
        for kind, target, protocol in (('fax', 'x', ''), ('network', '192.168.1.44', 'telnet'), ('usb', '../etc', '')):
            with self.assertRaises(ValueError):
                tools.harness_setup_device.func(runtime=None, kind=kind, target=target, protocol=protocol)

    def test_offered_ports_follow_the_launcher_without_restarting_the_gateway(self):
        from righaven import connections
        with patch.dict(os.environ, {'RIGHAVEN_DEVICES': '/dev/ttyUSB0'}):
            self.assertEqual(connections.local_devices(), ['/dev/ttyUSB0'])
            (self.reports / 'devices.json').write_text('{"devices":"/dev/ttyUSB0,/dev/ttyACM0,/dev/sda"}')
            self.assertEqual(connections.local_devices(), ['/dev/ttyUSB0', '/dev/ttyACM0'])
            (self.reports / 'devices.json').write_text('not json')
            self.assertEqual(connections.local_devices(), ['/dev/ttyUSB0'])



@unittest.skipUnless(tools, 'Gateway dependency environment required')
class ExploreToolTests(unittest.TestCase):
    def setUp(self):
        for p in (patch('righaven.host_bridge.pick', return_value=None), patch('righaven.tools.resolve_runtime_user_id', return_value='alice')):
            p.start()
            self.addCleanup(p.stop)

    def test_the_chat_uses_the_owners_agent_when_the_server_has_no_pc(self):
        from righaven import device_discovery
        with patch('righaven.host_bridge.pick', return_value='ag_0123456789ab'), \
             patch.object(device_discovery, 'explore_from_agent', return_value={'address': '192.168.50.20', 'ports': [80]}) as remote, \
             patch('righaven.host_bridge.run', return_value={'ok': True}) as run:
            tools.harness_explore_device.func(runtime=None, kind='network', target='192.168.50.20')
            tools.harness_explore_device.func(runtime=None, kind='bluetooth', target='38:A5:C9:3C:2E:9F')
        remote.assert_called_once_with('ag_0123456789ab', '192.168.50.20')
        run.assert_called_once_with('ble-inspect', {'address': '38:A5:C9:3C:2E:9F'}, timeout=150, agent='ag_0123456789ab')

    def test_the_chat_prepares_on_premise_devices_through_the_named_pc(self):
        from righaven import connections
        saved = []
        with patch('righaven.host_bridge.pick', return_value='ag_0123456789ab') as pick, \
             patch.object(connections, 'save', side_effect=lambda user, body: saved.append(body) or body), \
             patch.object(connections, 'listing', return_value=[]):
            tools.harness_setup_device.func(runtime=None, kind='com', target='com5', pc='PC casa')
            tools.harness_setup_device.func(runtime=None, kind='network', target='192.168.50.20', protocol='http', agent_network=True, pc='PC casa')
        pick.assert_called_with('alice', 'PC casa')
        self.assertEqual({k: saved[0][k] for k in ('transport', 'agent', 'device')}, {'transport': 'serial', 'agent': 'ag_0123456789ab', 'device': 'COM5'})
        self.assertEqual({k: saved[1][k] for k in ('transport', 'agent', 'host', 'protocol')},
                         {'transport': 'network', 'agent': 'ag_0123456789ab', 'host': '192.168.50.20', 'protocol': 'http'})
        for body in saved:  # what the chat prepares is what the page saves
            connections.validate({**body, 'id': 'x'})

    def test_the_chat_explores_like_the_page(self):
        from righaven import device_discovery
        with patch.object(device_discovery, 'explore', return_value={'address': '192.168.1.44', 'ports': [80]}):
            self.assertEqual(json.loads(tools.harness_explore_device.func(runtime=None, kind='network', target='192.168.1.44'))['ports'], [80])
        with patch('righaven.host_bridge.run', return_value={'ok': True, 'title': 'Tasmota'}) as run:
            tools.harness_explore_device.func(runtime=None, kind='wifi', target='tasmota-1A2B')
        run.assert_called_once_with('wifi-explore', {'ssid': 'tasmota-1A2B', 'hint': 'tasmota'}, timeout=120, agent=None)
        with patch('righaven.host_bridge.run', return_value={'devices': [{'busid': '1-4', 'name': 'CP210x'}]}):
            self.assertEqual(json.loads(tools.harness_explore_device.func(runtime=None, kind='usb', target='1-4'))['name'], 'CP210x')
            with self.assertRaises(ValueError):
                tools.harness_explore_device.func(runtime=None, kind='usb', target='9-9')
        with patch('righaven.host_bridge.run', return_value={'devices': [{'address': '192.168.1.30'}]}) as run:
            self.assertEqual(json.loads(tools.harness_explore_device.func(runtime=None, kind='listen', target=''))['devices'][0]['address'], '192.168.1.30')
        run.assert_called_once_with('net-listen', timeout=60, agent=None)
        with self.assertRaises(ValueError):
            tools.harness_explore_device.func(runtime=None, kind='fax', target='x')

if __name__ == '__main__':
    unittest.main()


@unittest.skipUnless(tools, 'Gateway dependency environment required')
class BluetoothToolTests(SetupDeviceToolTests):
    def test_ble_device_is_read_freely_and_written_only_once_approved(self):
        from righaven import connections, device_changes
        (self.host / 'heartbeat.json').write_text(json.dumps({'at': time.time(), 'platform': 'windows', 'actions': ['ble-inspect', 'ble-read', 'ble-write']}))
        created = json.loads(tools.harness_setup_device.func(runtime=None, kind='bluetooth', target='38:a5:c9:3c:2e:9f', name='Striscia LED'))
        self.assertEqual(created['connection']['transport'], 'bluetooth')
        self.assertEqual(connections.listing('alice')[0]['address'], '38:A5:C9:3C:2E:9F')
        with self.answering({'name': 'LED', 'services': [{'uuid': '0000ffe0-0000-1000-8000-00805f9b34fb', 'characteristics': []}]}):
            seen = json.loads(tools.harness_bluetooth.func(runtime=None, connection='striscia-led'))
        self.assertEqual(seen['name'], 'LED')
        request = json.loads(next((self.host / 'requests').glob('*.json')).read_text())
        self.assertEqual(request['args'], {'address': '38:A5:C9:3C:2E:9F'})
        workspace = Path(self.temp.name) / 'conversation'; workspace.mkdir()
        with patch('righaven.tools.workspace_for', return_value=workspace), self.answering({'ok': True}):
            refused = json.loads(tools.harness_bluetooth.func(runtime=None, connection='striscia-led', action='write', service='ffe0', characteristic='ffe1', value='7E 00 04'))
            self.assertFalse(refused['written'])
            command = device_changes.bluetooth_command({'payload': '7e0004', 'address': 'ffe0/ffe1'})
            self.assertEqual(command['address'], '0000ffe0-0000-1000-8000-00805f9b34fb/0000ffe1-0000-1000-8000-00805f9b34fb')
            with patch('righaven.device_changes._load', return_value=[{'id': 'c1', 'connection': 'striscia-led', 'status': 'approved',
                                                                         'fingerprint': device_changes.command_fingerprint(command)}]), \
                 patch('righaven.state.atomic_json') as saved, patch('righaven.audit_log.append'):
                done = json.loads(tools.harness_bluetooth.func(runtime=None, connection='striscia-led', action='write', service='ffe0', characteristic='ffe1', value='7E 00 04'))
            self.assertTrue(done['written'])
            self.assertEqual(saved.call_args[0][1][0]['status'], 'delivered')
            writes = [json.loads(p.read_text()) for p in (self.host / 'requests').glob('*.json')]
            self.assertIn({'address': '38:A5:C9:3C:2E:9F', 'service': '0000ffe0-0000-1000-8000-00805f9b34fb',
                           'characteristic': '0000ffe1-0000-1000-8000-00805f9b34fb', 'value': '7e0004'}, [w['args'] for w in writes if w['action'] == 'ble-write'])
        with self.assertRaises(ValueError):
            tools.harness_bluetooth.func(runtime=None, connection='missing')
        with self.answering({'value': '4c4544', 'text': 'LED'}):
            read = json.loads(tools.harness_bluetooth.func(runtime=None, address='38:A5:C9:3C:2E:9F', action='read', service='180a', characteristic='2a29'))
        self.assertEqual(read['text'], 'LED')
        with self.assertRaises(ValueError):
            tools.harness_bluetooth.func(runtime=None, address='38:A5:C9:3C:2E:9F', action='write', service='ffe0', characteristic='ffe1', value='01')
