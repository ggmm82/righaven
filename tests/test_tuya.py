"""Tuya / Smart Life devices over the local protocol: connection fields, reads and approved writes."""
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
import iot_tools  # noqa: E402
from righaven import connections  # noqa: E402


class FakeDevice:
    state = {'1': False, '3': 20}
    created = []

    def __init__(self, dev_id, address, local_key, version, connection_timeout):
        FakeDevice.created.append((dev_id, address, local_key, version))
        self.closed = False

    def set_socketRetryLimit(self, value): pass
    def set_socketTimeout(self, value): pass
    def status(self): return {'dps': dict(FakeDevice.state)}
    def set_multiple_values(self, values):
        FakeDevice.state.update(values)
        return {'dps': values}
    def close(self): self.closed = True


class TuyaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'out'
        self.output.mkdir()
        FakeDevice.state = {'1': False, '3': 20}
        FakeDevice.created = []
        module = types.ModuleType('tinytuya')
        module.Device = FakeDevice
        patcher = patch.dict(sys.modules, {'tinytuya': module})
        patcher.start()
        self.addCleanup(patcher.stop)

    def record(self, **values):
        body = {'kind': 'device', 'id': 'presa', 'name': 'Presa', 'transport': 'network', 'protocol': 'tuya', 'host': '192.168.1.44',
                'username': 'bf1234567890abcdefgh', 'password': '0123456789abcdef', 'access': 'write', **values}
        return connections.validate(body)

    def test_connection_needs_device_id_local_key_and_version(self):
        record = self.record(version='3.4')
        self.assertEqual((record['port'], record['version'], record['tls']), (6668, '3.4', False))
        delivered = connections.device_file(record)
        self.assertEqual((delivered['url'], delivered['username'], delivered['password'], delivered['version']),
                         ('tuya://192.168.1.44:6668', 'bf1234567890abcdefgh', '0123456789abcdef', '3.4'))
        self.assertNotIn('password', connections.public_view(record))
        for bad in ({'username': 'x'}, {'password': ''}, {'version': '9'}):
            with self.assertRaises(ValueError):
                self.record(**bad)

    def cfg(self, approvals=()):
        return {**connections.device_file(self.record()), 'write_enabled': True, 'approvals': list(approvals)}

    def test_status_reads_data_points(self):
        result = iot_job.tuya(self.cfg(), {'command': 'status'}, self.output)
        self.assertEqual(result['dps'], {'1': False, '3': 20})
        self.assertEqual(FakeDevice.created[0], ('bf1234567890abcdefgh', '192.168.1.44', '0123456789abcdef', 3.3))
        self.assertTrue((self.output / 'status.json').is_file())

    def test_set_needs_the_approval_of_that_exact_command_and_reads_back(self):
        args = {'command': 'set', 'payload': '{"1": true}', 'encoding': 'json'}
        with self.assertRaisesRegex(iot_job.UserError, 'owner approval'):
            iot_job.tuya(self.cfg(), args, self.output)
        self.assertFalse(FakeDevice.state['1'])
        other = iot_job.command_fingerprint({'payload': '{"1": false}', 'encoding': 'json'})
        with self.assertRaisesRegex(iot_job.UserError, 'owner approval'):
            iot_job.tuya(self.cfg([{'id': 'a1', 'action': 'send', 'fingerprint': other}]), args, self.output)
        approval = {'id': 'a2', 'action': 'send', 'fingerprint': iot_job.command_fingerprint(args)}
        result = iot_job.tuya(self.cfg([approval]), args, self.output)
        self.assertEqual((result['status'], result['approval'], result['after']['1']), ('passed', 'a2', True))
        self.assertEqual(json.loads((self.output / 'set.json').read_text())['before']['1'], False)

    def test_invalid_values_and_wrong_connections_are_refused(self):
        with self.assertRaises(iot_job.UserError):
            iot_job.tuya_values('{"switch": true}')
        with self.assertRaises(iot_job.UserError):
            iot_job.tuya_values('[1]')
        self.assertTrue(iot_tools.writes('tuya', {'command': 'set'}))
        self.assertFalse(iot_tools.writes('tuya', {'command': 'status'}))
        folder = Path(self.temp.name) / 'connections'
        folder.mkdir()
        (folder / 'mqtt.json').write_text(json.dumps({'kind': 'device', 'protocol': 'mqtt', 'write_enabled': True}))
        with patch.object(iot_tools, 'CONNECTIONS', folder):
            with self.assertRaisesRegex(ValueError, 'not a Tuya'):
                iot_tools.connection('mqtt', 'tuya', {'command': 'status'})


if __name__ == '__main__':
    unittest.main()
