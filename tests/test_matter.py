"""Matter devices through the RigHaven Matter controller (python-matter-server WebSocket API)."""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(1, str(ROOT))
import iot_job  # noqa: E402
from righaven import connections, matter  # noqa: E402

NODE = {'node_id': 5, 'available': True, 'attributes': {'0/40/1': 'IKEA', '0/40/3': 'TRADFRI bulb', '1/6/0': False, '1/8/0': 128,
                                                          '2/1026/0': 2150, '1/29/0': []}}


class FakeController:
    """Answers like python-matter-server: server info first, then one result per message_id."""
    calls = []
    nodes = []

    def __init__(self, url, **kwargs):
        self.url, self.outbox = url, [json.dumps({'fabric_id': 1, 'schema_version': 11})]

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def send(self, text):
        message = json.loads(text)
        FakeController.calls.append((message['command'], message['args']))
        command, args = message['command'], message['args']
        self.outbox.append(json.dumps({'message_id': 'other', 'event': 'attribute_updated'}))
        if command == 'get_nodes':
            result = FakeController.nodes
        elif command == 'commission_with_code':
            if args['code'] != '34970112332':
                self.outbox.append(json.dumps({'message_id': message['message_id'], 'error_code': 1, 'details': 'Commissioning failed'}))
                return
            FakeController.nodes.append(json.loads(json.dumps(NODE)))
            result = FakeController.nodes[-1]
        elif command == 'device_command':
            FakeController.nodes[0]['attributes']['1/6/0'] = args['command_name'] == 'On'
            result = None
        elif command == 'read_attribute':
            result = FakeController.nodes[0]['attributes'].get(args['attribute_path'])
        else:
            result = None
        self.outbox.append(json.dumps({'message_id': message['message_id'], 'result': result}))

    def recv(self, timeout=None):
        return self.outbox.pop(0)


class MatterTests(unittest.TestCase):
    def setUp(self):
        FakeController.calls, FakeController.nodes = [], []
        client = types.ModuleType('websockets.sync.client')
        client.connect = FakeController
        modules = {'websockets': types.ModuleType('websockets'), 'websockets.sync': types.ModuleType('websockets.sync'), 'websockets.sync.client': client}
        for patcher in (patch.dict(sys.modules, modules), patch.dict(os.environ, {'RIGHAVEN_MATTER_URL': 'ws://172.30.42.1:5580/ws',
                                                                                   'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'})):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_controller_off_is_explained(self):
        with patch.dict(os.environ, {'RIGHAVEN_MATTER_URL': ''}):
            self.assertEqual(matter.status(), {'available': False, 'nodes': []})
            with self.assertRaisesRegex(ValueError, 'matter enable'):
                matter.commission('3497-011-2332')

    def test_commission_status_and_command(self):
        with self.assertRaisesRegex(ValueError, 'Codice Matter non valido'):
            matter.commission('1234')
        node = matter.commission('3497-011-2332')
        self.assertEqual(FakeController.calls[-1], ('commission_with_code', {'code': '34970112332', 'network_only': True}))
        self.assertEqual((node['node_id'], node['name'], node['vendor'], node['switchable']), (5, 'TRADFRI bulb', 'IKEA', [1]))
        self.assertEqual(node['readings']['temperature'], {'value': 21.5, 'unit': '°C', 'endpoint': 2})
        with self.assertRaisesRegex(ValueError, 'Commissioning failed'):
            matter.commission('11111111111')
        matter.command(5, 1, 'On')
        self.assertEqual(FakeController.calls[-1][1], {'node_id': 5, 'endpoint_id': 1, 'cluster_id': 6, 'command_name': 'On', 'payload': {}})
        self.assertTrue(matter.status()['nodes'][0]['readings']['on']['value'])
        with self.assertRaises(ValueError):
            matter.command(5, 1, 'Explode')

    def test_connection_and_worker_operation_need_approval_for_commands(self):
        FakeController.nodes.append(json.loads(json.dumps(NODE)))
        record = connections.validate({'kind': 'device', 'id': 'lampada', 'name': 'Lampada', 'transport': 'network', 'protocol': 'matter',
                                       'host': '172.30.42.1', 'port': 5580, 'node_id': 5, 'access': 'write'})
        cfg = {**connections.device_file(record), 'write_enabled': True, 'approvals': []}
        self.assertEqual((cfg['url'], cfg['node_id']), ('ws://172.30.42.1:5580/ws', 5))
        with self.assertRaises(ValueError):
            connections.validate({'kind': 'device', 'id': 'x', 'name': 'x', 'transport': 'network', 'protocol': 'matter', 'host': '172.30.42.1'})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            self.assertEqual(iot_job.matter(cfg, {'command': 'read', 'attribute_path': '1/8/0'}, output)['value'], 128)
            self.assertEqual(iot_job.matter(cfg, {'command': 'status'}, output)['attributes'], 6)
            args = {'command': 'command', 'payload': '{"endpoint": 1, "cluster": 6, "command": "On"}', 'encoding': 'json'}
            with self.assertRaisesRegex(iot_job.UserError, 'owner approval'):
                iot_job.matter(cfg, args, output)
            cfg['approvals'] = [{'id': 'm1', 'action': 'send', 'fingerprint': iot_job.command_fingerprint(args)}]
            result = iot_job.matter(cfg, args, output)
            self.assertEqual((result['approval'], result['before']['1/6/0'], result['after']['1/6/0']), ('m1', False, True))
            with self.assertRaises(iot_job.UserError):
                iot_job.matter_request('{"endpoint": "1", "cluster": 6, "command": "On"}')


if __name__ == '__main__':
    unittest.main()
