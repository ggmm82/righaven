"""iot toolkit: consent checks, deterministic simulation and telemetry summaries."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(1, str(ROOT))
import iot_job  # noqa: E402
import iot_tools  # noqa: E402
from extended_specs import TOOLS  # noqa: E402

SCENARIO = {'start': '2026-03-02T00:00:00+00:00', 'duration_hours': 48, 'interval_seconds': 1800, 'seed': 3,
            'devices': [{'group': 'bus', 'count': 2, 'weekend_factor': 0.5,
                         'sensors': [{'name': 'passengers', 'mode': 'count', 'baseline': 40, 'noise': 5, 'profile': 'commute', 'unit': 'people'}]},
                        {'group': 'bin', 'count': 3,
                         'sensors': [{'name': 'fill', 'mode': 'accumulate', 'rate_per_hour': 5, 'noise': 0.1, 'profile': 'daytime',
                                      'start': 5, 'reset_at': 90, 'max': 100, 'unit': '%'}]}],
            'events': [{'group': 'bus', 'sensor': 'passengers', 'start': '2026-03-02T17:00:00+00:00', 'end': '2026-03-02T19:00:00+00:00', 'factor': 3}]}


class IotToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def output(self, name):
        folder = self.root / name
        (folder / 'Sources').mkdir(parents=True)
        return folder

    def test_operations_are_registered_with_bounded_schemas(self):
        names = [t['name'] for t in TOOLS['iot']]
        self.assertEqual(names, ['iot.capture', 'iot.send', 'iot.simulate', 'iot.inspect', 'iot.flash', 'iot.android', 'iot.obd', 'iot.tuya', 'iot.matter'])
        for spec in TOOLS['iot']:
            self.assertFalse(spec['inputSchema']['additionalProperties'])
            self.assertIn('output', spec['inputSchema']['required'])
        capture = next(t for t in TOOLS['iot'] if t['name'] == 'iot.capture')['inputSchema']['properties']
        self.assertEqual((capture['seconds']['maximum'], capture['max_records']['maximum']), (600, 100000))

    def test_devices_need_an_assigned_connection_and_write_consent(self):
        folder = self.root / 'connections'
        folder.mkdir()
        (folder / 'sensori.json').write_text(json.dumps({'kind': 'device', 'transport': 'network', 'protocol': 'mqtt', 'write_enabled': False}))
        (folder / 'erp.json').write_text(json.dumps({'kind': 'sqlserver'}))
        (folder / 'esp.json').write_text(json.dumps({'kind': 'device', 'transport': 'serial', 'write_enabled': True}))
        with patch.object(iot_tools, 'CONNECTIONS', folder):
            self.assertEqual(iot_tools.connection('sensori', 'capture')[1]['protocol'], 'mqtt')
            with self.assertRaisesRegex(ValueError, 'not allowed'):
                iot_tools.connection('sensori', 'send')
            with self.assertRaisesRegex(ValueError, 'not available'):
                iot_tools.connection('altro', 'capture')
            with self.assertRaisesRegex(ValueError, 'not a device'):
                iot_tools.connection('erp', 'capture')
            with self.assertRaisesRegex(ValueError, 'Use the ID'):
                iot_tools.connection('../etc', 'capture')
            self.assertTrue(iot_tools.connection('esp', 'flash')[1]['write_enabled'])
        config = self.root / 'cfg.json'
        config.write_text(json.dumps({'kind': 'device', 'transport': 'network', 'protocol': 'mqtt', 'write_enabled': False}))
        request = self.root / 'request.json'
        request.write_text(json.dumps({'action': 'send', 'args': {'topic': 'x', 'payload': '1'}, 'output': str(self.output('send')), 'connection_file': str(config)}))
        with self.assertRaisesRegex(iot_job.UserError, 'not allowed'):
            iot_job.main(str(request))  # the job checks again inside the worker

    def test_simulation_is_deterministic_bounded_and_follows_the_scenario(self):
        source = self.root / 'scenario.json'
        source.write_text(json.dumps(SCENARIO))
        first = iot_job.simulate({}, str(source), self.output('one'))
        second = iot_job.simulate({}, str(source), self.output('two'))
        self.assertEqual(first['readings'], 5 * 96)
        self.assertEqual((self.root / 'one/telemetry.jsonl').read_bytes(), (self.root / 'two/telemetry.jsonl').read_bytes())
        self.assertTrue((self.root / 'one/Sources/scenario.json').is_file(), 'the scenario is kept as a source')
        rows = [json.loads(line) for line in (self.root / 'one/telemetry.jsonl').read_text().splitlines()]
        fill = [r['value'] for r in rows if r['sensor'] == 'fill']
        self.assertTrue(5 <= min(fill) and max(fill) <= 90, 'accumulating sensors reset at the threshold')
        peak = [r['value'] for r in rows if r['sensor'] == 'passengers' and r['t'].startswith('2026-03-02T18')]
        night = [r['value'] for r in rows if r['sensor'] == 'passengers' and r['t'].startswith('2026-03-02T03')]
        self.assertGreater(min(peak), max(night) * 3, 'profile and event shape the counts')
        summary = json.loads((self.root / 'one/summary.json').read_text())
        self.assertEqual(set(summary['sensors']), {'bus.passengers', 'bin.fill'})
        self.assertIn('Synthetic', ' '.join(first['limits']))
        for bad in ({'devices': []}, {**SCENARIO, 'duration_hours': 10000}, {**SCENARIO, 'devices': [{'group': 'a b', 'sensors': [{'name': 'x'}]}]},
                    {**SCENARIO, 'devices': [{'group': 'a', 'count': 6000, 'sensors': [{'name': 'x'}]}]},
                    {**SCENARIO, 'devices': [{'group': 'a', 'sensors': [{'name': 'x', 'profile': 'random'}]}]}):
            source.write_text(json.dumps(bad))
            with self.subTest(bad=str(bad)[:60]), self.assertRaises(iot_job.UserError):
                iot_job.simulate({}, str(source), self.output('bad-' + str(abs(hash(str(bad))))))

    def test_telemetry_summary_reads_json_and_key_value_lines(self):
        folder = self.output('capture')
        record = iot_job.Recorder(folder, 3)
        self.assertTrue(record.add({'source': 'a', 'value': '{"temp": 21.5, "nested": {"hum": 40}}'}))
        self.assertTrue(record.add({'source': 'b', 'value': 'T=22.5 H:41'}))
        self.assertTrue(record.add({'source': 'c', 'value': {'1': 10, '2': 20}}))
        self.assertFalse(record.add({'source': 'd', 'value': '1'}), 'max_records bounds the capture')
        summary = record.close(3.0)
        self.assertEqual(summary['records'], 3)
        self.assertEqual(set(summary['numeric_fields']), {'temp', 'nested.hum', 'T', 'H', '1', '2'})
        self.assertEqual((folder / 'telemetry.csv').read_text().splitlines()[0], 't,source,value')

    def test_payload_encodings(self):
        self.assertEqual(iot_job.payload({'payload': '0aff', 'encoding': 'hex'}), b'\n\xff')
        self.assertEqual(iot_job.payload({'payload': '{"on": true}', 'encoding': 'json'}), b'{"on": true}')
        for bad in ({'payload': 'xyz', 'encoding': 'hex'}, {'payload': '{', 'encoding': 'json'}, {'payload': 'a' * 70000}):
            with self.subTest(bad=bad['payload'][:5]), self.assertRaises(iot_job.UserError):
                iot_job.payload(bad)

    @unittest.skipUnless(os.path.exists('/dev/ptmx'), 'needs pseudo terminals')
    def test_local_serial_is_read_without_write_access(self):
        import pty
        import threading
        import time
        master, slave = pty.openpty()
        path = os.ttyname(slave)

        def feed():
            time.sleep(0.5)
            os.write(master, b'T=20\r\nT=21\r\n')
        threading.Thread(target=feed).start()
        result = iot_job.capture({'transport': 'local', 'url': path, 'baud': 9600}, {'seconds': 2}, self.output('serial'))
        self.assertEqual(result['records'], 2)
        port = iot_job.ReadOnlyTTY(path, 9600)
        with self.assertRaisesRegex(iot_job.UserError, 'not allowed'):
            port.write(b'x')
        port.close()


    def test_every_write_needs_the_exact_approved_change_once(self):
        from righaven.device_changes import command_fingerprint
        command = {'topic': 'casa/luce', 'payload': 'on'}
        same = {'topic': 'casa/luce', 'payload': 'on', 'encoding': 'text', 'retain': False}
        self.assertEqual(command_fingerprint(command), iot_job.command_fingerprint(same), 'gateway and worker agree; defaults do not matter')
        self.assertNotEqual(iot_job.command_fingerprint(command), iot_job.command_fingerprint({**command, 'payload': 'off'}))
        cfg = {'approvals': [{'id': 'a1', 'action': 'send', 'fingerprint': command_fingerprint(command)}]}
        with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
            iot_job.approved(cfg, 'send', fingerprint=iot_job.command_fingerprint({**command, 'payload': 'off'}))
        self.assertEqual(iot_job.approved(cfg, 'send', fingerprint=iot_job.command_fingerprint(same)), 'a1')
        with self.assertRaisesRegex(iot_job.UserError, 'approval'):
            iot_job.approved(cfg, 'send', fingerprint=iot_job.command_fingerprint(same))  # used once

    def test_send_and_flash_refuse_without_an_approval(self):
        cfg = {'kind': 'device', 'transport': 'network', 'protocol': 'tcp', 'host': '127.0.0.1', 'port': 9, 'write_enabled': True}
        with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
            iot_job.send(cfg, {'payload': 'x'}, self.output('send'))
        image = self.root / 'fw.bin'
        image.write_bytes(b'firmware')
        serial_cfg = {'transport': 'serial', 'url': 'rfc2217://127.0.0.1:9', 'write_enabled': True,
                      'approvals': [{'id': 'f1', 'action': 'flash', 'sha256': 'other'}]}
        with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
            iot_job.flash(serial_cfg, {}, str(image), self.output('flash'))

    def approved_send(self, cfg, command):
        from righaven.device_changes import command_fingerprint
        return {**cfg, 'write_enabled': True, 'approvals': [{'id': 's1', 'action': 'send', 'fingerprint': command_fingerprint(command)}]}

    def test_tcp_reply_ends_at_the_prompt(self):
        import socket
        import threading
        import time
        server = socket.socket()
        server.bind(('127.0.0.1', 0))
        server.listen(1)
        self.addCleanup(server.close)

        def answer():
            connection, _ = server.accept()
            with connection:
                connection.recv(64)
                connection.sendall(b'43 01 33\r\r>')  # an ELM327 answer: no newline after the prompt
                time.sleep(3)
        threading.Thread(target=answer, daemon=True).start()
        cfg = self.approved_send({'transport': 'network', 'protocol': 'tcp', 'host': '127.0.0.1', 'port': server.getsockname()[1], 'url': 'tcp://x'},
                                 {'payload': '03\r'})
        started = time.monotonic()
        result = iot_job.send(cfg, {'payload': '03\r', 'reply_seconds': 10, 'reply_until': '>'}, self.output('tcp'))
        self.assertLess(time.monotonic() - started, 5, 'the prompt ends the reply before reply_seconds')
        self.assertEqual(result['reply_records'], 2)
        rows = [json.loads(line) for line in (self.root / 'tcp' / 'telemetry.jsonl').read_text().splitlines()]
        self.assertEqual([r['value'] for r in rows], ['43 01 33', '>'])
        self.assertEqual(iot_job.reply_until({'reply_until': '3e', 'encoding': 'hex'}), b'>')
        with self.assertRaises(iot_job.UserError):
            iot_job.reply_until({'reply_until': 'zz', 'encoding': 'hex'})

    def test_mqtt_reply_topic_is_subscribed_before_publishing(self):
        events = []

        class Message:
            def __init__(self, topic, payload):
                self.topic, self.payload, self.retain = topic, payload, False

        class Published:
            def wait_for_publish(self, timeout):
                pass

            def is_published(self):
                return True

        class Client:
            on_message = on_subscribe = None

            def connect(self, host, port, keepalive):
                events.append('connect')

            def loop_start(self):
                pass

            def loop_stop(self):
                pass

            def disconnect(self):
                events.append('disconnect')

            def subscribe(self, topic, qos):
                events.append('subscribe ' + topic)
                self.on_subscribe(self, None, 1, [0], None)

            def publish(self, topic, data, qos, retain):
                events.append('publish ' + topic)
                # The device answers at once, on its status topic and outside the connection's filter.
                self.on_message(self, None, Message('stat/plug/POWER', b'ON'))
                self.on_message(self, None, Message('other/secret', b'x'))
                return Published()

        command = {'topic': 'cmnd/plug/POWER', 'payload': 'ON'}
        cfg = self.approved_send({'transport': 'network', 'protocol': 'mqtt', 'host': 'broker', 'port': 1883, 'topic': 'stat/plug/#'}, command)
        with patch.object(iot_job, 'mqtt_client', return_value=Client()):
            result = iot_job.send(cfg, {**command, 'reply_topic': 'stat/plug/#', 'reply_seconds': 5, 'reply_until': 'ON'}, self.output('mqtt'))
        self.assertEqual(events, ['connect', 'subscribe stat/plug/#', 'publish cmnd/plug/POWER', 'disconnect'])
        self.assertEqual(result['reply_records'], 1)
        self.assertEqual(result['written']['reply_topic'], 'stat/plug/#')
        with patch.object(iot_job, 'mqtt_client', return_value=Client()), self.assertRaises(iot_job.UserError):
            iot_job.send(self.approved_send(cfg, command), {**command, 'reply_topic': 'stat/#/x'}, self.output('mqtt-bad'))

    def test_mqtt_topic_filters(self):
        self.assertTrue(iot_job.topic_matches('stat/plug/#', 'stat/plug/POWER'))
        self.assertTrue(iot_job.topic_matches('stat/+/POWER', 'stat/plug/POWER'))
        self.assertTrue(iot_job.topic_matches('#', 'a/b'))
        self.assertFalse(iot_job.topic_matches('#', '$SYS/load'))
        self.assertFalse(iot_job.topic_matches('stat/+', 'stat/plug/POWER'))
        self.assertFalse(iot_job.topic_matches('stat/plug', 'other/plug'))
        self.assertTrue(iot_job.valid_filter('stat/+/#') and not iot_job.valid_filter('stat/#/x') and not iot_job.valid_filter('st+at'))

    def fake_adb(self, state='device'):
        """A stand-in adb that answers like an Android TV and records its calls."""
        folder = self.root / 'bin'
        folder.mkdir(exist_ok=True)
        log = self.root / 'adb-calls.txt'
        script = folder / 'adb'
        script.write_text(f"""#!/bin/sh
echo "$@" >> {log}
case "$*" in
  *get-state*) echo {state};;
  *devices*) echo "List of devices attached";;
  *getprop*) printf '[ro.product.model]: [Smart TV]\\n[ro.build.version.release]: [11]\\n[ro.build.fingerprint]: [tv/x:11/1]\\n';;
  *"list packages -d"*) [ -f {self.root}/disabled ] && echo package:com.vendor.ads;;
  *"list packages -3"*) echo package:com.example.app;;
  *"list packages"*) printf 'package:com.example.app\\npackage:com.vendor.ads\\n';;
  *disable-user*) touch {self.root}/disabled;;
esac
exit 0
""")
        script.chmod(0o755)
        return folder, log

    def test_android_reads_freely_and_changes_only_what_was_approved(self):
        folder, log = self.fake_adb()
        cfg = {'kind': 'device', 'transport': 'network', 'protocol': 'adb', 'host': '192.168.1.50', 'port': 5555, 'adb_key': 'KEY', 'write_enabled': True,
               'approvals': [{'id': 'd1', 'action': 'disable', 'package': 'com.vendor.ads'}]}
        with patch.dict(os.environ, {'PATH': str(folder) + os.pathsep + os.environ['PATH']}):
            info = iot_job.android(cfg, {'command': 'info'}, None, self.output('info'))
            self.assertEqual((info['device']['model'], info['device']['android'], info['device']['packages']), ('Smart TV', '11', 2))
            with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
                iot_job.android(cfg, {'command': 'uninstall', 'package': 'com.vendor.ads'}, None, self.output('uninstall'))
            done = iot_job.android(cfg, {'command': 'disable', 'package': 'com.vendor.ads'}, None, self.output('disable'))
            self.assertEqual((done['status'], done['approval'], done['disabled']), ('passed', 'd1', True))
            with self.assertRaisesRegex(iot_job.UserError, 'package'):
                iot_job.android(cfg, {'command': 'enable', 'package': 'bad;rm'}, None, self.output('bad'))
        calls = log.read_text()
        self.assertIn('connect 192.168.1.50:5555', calls)
        self.assertNotIn('uninstall', calls, 'nothing reaches the device without approval')
        self.assertEqual([p for p in Path(tempfile.gettempdir()).iterdir() if p.name.startswith('righaven-adb-')], [],
                         'the device key is removed with the job')

    def test_android_sideload_needs_the_device_in_sideload_mode(self):
        folder, _ = self.fake_adb(state='device')
        update = self.root / 'ota.zip'
        update.write_bytes(b'ota')
        import hashlib
        cfg = {'kind': 'device', 'transport': 'network', 'protocol': 'adb', 'host': '10.0.0.5', 'port': 5555, 'adb_key': 'KEY', 'write_enabled': True,
               'approvals': [{'id': 's1', 'action': 'sideload', 'sha256': hashlib.sha256(b'ota').hexdigest()}]}
        with patch.dict(os.environ, {'PATH': str(folder) + os.pathsep + os.environ['PATH']}), self.assertRaisesRegex(iot_job.UserError, 'sideload mode'):
            iot_job.android(cfg, {'command': 'sideload'}, str(update), self.output('ota'))

    def test_obd_reads_codes_and_clears_them_only_with_approval(self):
        import types

        class Value:
            def __init__(self, value):
                self.value = value

            def is_null(self):
                return self.value is None

        class Quantity:
            def __init__(self, magnitude, units):
                self.magnitude, self.units = magnitude, units

        state = {'codes': [('P0301', 'Cylinder 1 Misfire Detected')]}

        class Command:
            def __init__(self, name):
                self.name = name

        names = ('ELM_VERSION', 'ELM_VOLTAGE', 'GET_DTC', 'CLEAR_DTC', 'RPM', 'SPEED')
        commands = types.SimpleNamespace(**{n: Command(n) for n in names})

        class Connection:
            supported_commands = {commands.RPM, commands.SPEED}

            def __init__(self, port, **kwargs):
                self.port = port

            def is_connected(self):
                return True

            def status(self):
                return 'Car Connected'

            def protocol_name(self):
                return 'ISO 15765-4 (CAN 11/500)'

            def query(self, command, force=False):
                if command.name == 'GET_DTC':
                    return Value(list(state['codes']))
                if command.name == 'CLEAR_DTC':
                    state['codes'] = []
                    return Value(None)
                if command.name == 'RPM':
                    return Value(Quantity(850.0, 'revolutions_per_minute'))
                if command.name == 'ELM_VOLTAGE':
                    return Value(Quantity(12.6, 'volt'))
                return Value(None)

            def close(self):
                pass

        fake = types.SimpleNamespace(OBD=Connection, commands=commands)
        cfg = {'kind': 'device', 'transport': 'network', 'protocol': 'tcp', 'host': '192.168.0.10', 'port': 35000, 'write_enabled': True}
        with patch.dict(sys.modules, {'obd': fake}):
            self.assertEqual(iot_job.obd_port(cfg), 'socket://192.168.0.10:35000', 'Wi-Fi adapters through pyserial sockets')
            codes = iot_job.vehicle(cfg, {'command': 'codes'}, self.output('codes'))
            self.assertEqual(codes['stored_codes'], [['P0301', 'Cylinder 1 Misfire Detected']])
            live = iot_job.vehicle(cfg, {'command': 'live', 'pids': ['RPM'], 'seconds': 1, 'interval_seconds': 0.2}, self.output('live'))
            self.assertIn('RPM', live['numeric_fields'])
            with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
                iot_job.vehicle(cfg, {'command': 'clear_codes'}, self.output('clear-refused'))
            self.assertTrue(state['codes'], 'nothing cleared without approval')
            cleared = iot_job.vehicle({**cfg, 'approvals': [{'id': 'c1', 'action': 'clear_codes'}]}, {'command': 'clear_codes'}, self.output('clear'))
            self.assertEqual((cleared['approval'], cleared['codes_after']), ('c1', []))
            # The adapter answers but the vehicle does not: the adapter's version and voltage are still a result.
            silent = type('Silent', (Connection,), {'is_connected': lambda self: False, 'status': lambda self: 'OBD Connected'})
            with patch.object(fake, 'OBD', silent):
                quiet = iot_job.vehicle(cfg, {'command': 'codes'}, self.output('quiet'))
            self.assertEqual(quiet['status'], 'no_vehicle')
            self.assertEqual(quiet['adapter']['elm_voltage'], {'value': 12.6, 'unit': 'volt'})
            self.assertIn('physical limit', quiet['limits'][0])
            absent = type('Absent', (Connection,), {'is_connected': lambda self: False, 'status': lambda self: 'Not Connected'})
            with patch.object(fake, 'OBD', absent), self.assertRaisesRegex(iot_job.UserError, 'adapter not responding'):
                iot_job.vehicle(cfg, {'command': 'info'}, self.output('absent'))

    def test_the_owner_zone_of_trust_covers_writes_inside_the_task(self):
        cfg = {'approvals': [], 'auto_approve': ['send'], 'auto_until': ''}
        self.assertEqual(iot_job.approved(cfg, 'send', fingerprint='anything'), 'zone-of-trust')
        with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
            iot_job.approved(cfg, 'flash', sha256='x')
        with self.assertRaisesRegex(iot_job.UserError, 'harness_device_change'):
            iot_job.approved({**cfg, 'auto_until': '2000-01-01T00:00:00Z'}, 'send', fingerprint='anything')
        exact = {**cfg, 'approvals': [{'id': 'a1', 'action': 'send', 'fingerprint': 'f'}]}
        self.assertEqual(iot_job.approved(exact, 'send', fingerprint='f'), 'a1', 'an exact approval is used first')


if __name__ == '__main__':
    unittest.main()
