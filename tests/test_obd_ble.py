import json
import unittest
from unittest.mock import patch

from righaven import host_bridge, obd_ble

try:
    from righaven import tools
except ImportError:  # gateway dependencies missing
    tools = None


def hexed(text):
    return text.encode().hex()


ADAPTER = [{'uuid': '0000180a-0000-1000-8000-00805f9b34fb', 'characteristics': [{'uuid': '00002a29-0000-1000-8000-00805f9b34fb', 'properties': ['Read']}]},
           {'uuid': '0000fff0-0000-1000-8000-00805f9b34fb', 'characteristics': [
               {'uuid': '0000fff1-0000-1000-8000-00805f9b34fb', 'properties': ['Read', 'Notify']},
               {'uuid': '0000fff2-0000-1000-8000-00805f9b34fb', 'properties': ['Write', 'WriteWithoutResponse']}]}]


def answers(request, overrides):
    canned = {'ATZ': '\r\rELM327 v1.5\r\r>', 'ATRV': '12.4V\r\r>', '0100': 'SEARCHING...\r4100BE3FA813\r\r>', 'ATDPN': 'A6\r\r>',
              '0101': '41018307E100\r\r>', '03': '430201330171\r\r>', '07': '4700\r\r>', '0A': 'NO DATA\r\r>'}
    canned.update(overrides)
    return [hexed(canned.get(c, 'OK\r\r>')) for c in obd_ble.commands(request)]


class ObdBleTests(unittest.TestCase):
    def test_only_fixed_read_requests_reach_the_adapter(self):
        for request in ('codes', 'live', 'info'):
            sent = obd_ble.commands(request)
            self.assertLessEqual(len(sent), 16)
            self.assertTrue(all(obd_ble.encode(c).endswith('0d') for c in sent))
            self.assertNotIn('04', sent)
        for forbidden in ('04', 'ATPP', '2E0101'):
            with self.assertRaises(ValueError):
                obd_ble.encode(forbidden)
        with self.assertRaises(ValueError):
            obd_ble.commands('clear')
        joined = ','.join(obd_ble.encode(c) for c in obd_ble.commands('live'))
        self.assertTrue(host_bridge.ARGUMENTS['commands'].fullmatch(joined))

    def test_adapter_channel_is_found(self):
        self.assertEqual(obd_ble.pick(ADAPTER), ('0000fff0-0000-1000-8000-00805f9b34fb', '0000fff2-0000-1000-8000-00805f9b34fb',
                                                 '0000fff1-0000-1000-8000-00805f9b34fb'))
        other = [{'uuid': '0000ae30-0000-1000-8000-00805f9b34fb', 'characteristics': [
            {'uuid': '0000ae01-0000-1000-8000-00805f9b34fb', 'properties': ['WriteWithoutResponse']},
            {'uuid': '0000ae02-0000-1000-8000-00805f9b34fb', 'properties': ['Notify']}]}]
        self.assertEqual(obd_ble.pick(other)[1:], ('0000ae01-0000-1000-8000-00805f9b34fb', '0000ae02-0000-1000-8000-00805f9b34fb'))
        with self.assertRaises(ValueError):
            obd_ble.pick(ADAPTER[:1])

    def test_codes_are_decoded_for_can_and_older_protocols(self):
        result = obd_ble.decode('codes', obd_ble.commands('codes'), answers('codes', {}))
        self.assertEqual(result['adapter'], 'ELM327 v1.5')
        self.assertEqual(result['battery_voltage'], '12.4V')
        self.assertTrue(result['vehicle_answers'] and result['mil_on'])
        self.assertEqual(result['stored_code_count'], 3)
        self.assertEqual([c['code'] for c in result['stored']], ['P0133', 'P0171'])
        self.assertEqual(result['pending'], [])
        self.assertEqual(result['permanent'], [])
        self.assertTrue(result['stored'][0]['generic'])
        # Multi-frame CAN answer with three codes (one manufacturer code) and an ISO 9141 answer.
        multi = obd_ble.decode('codes', obd_ble.commands('codes'), answers('codes', {'03': '00A\r0:430301330171\r1:C1230000000000\r\r>'}))
        self.assertEqual([c['code'] for c in multi['stored']], ['P0133', 'P0171', 'U0123'])
        legacy = obd_ble.decode('codes', obd_ble.commands('codes'), answers('codes', {'ATDPN': '3\r\r>', '03': '43 01 33 01 71 00 00\r\r>'}))
        self.assertEqual([c['code'] for c in legacy['stored']], ['P0133', 'P0171'])
        self.assertFalse(obd_ble.describe('P1234')['generic'])

    def test_live_values_and_silent_vehicle(self):
        live = obd_ble.decode('live', obd_ble.commands('live'), answers('live', {'010C': '410C1AF8\r\r>', '0105': '41057B\r\r>', '010D': 'NO DATA\r\r>'}))
        self.assertEqual(live['values']['rpm'], 1726.0)
        self.assertEqual(live['values']['coolant_c'], 83)
        self.assertIsNone(live['values']['speed_kmh'])
        silent = obd_ble.decode('codes', obd_ble.commands('codes'), answers('codes', {'0100': 'SEARCHING...\rUNABLE TO CONNECT\r\r>', '03': 'NO DATA\r\r>'}))
        self.assertFalse(silent['vehicle_answers'])
        self.assertIn('ignition on', silent['problem'])
        empty = obd_ble.decode('codes', obd_ble.commands('codes'), [])
        self.assertIn('did not answer', empty['problem'])

    def test_vin(self):
        info = obd_ble.decode('info', obd_ble.commands('info'), answers('info', {
            '0902': '014\r0:490201314734\r1:4A4335443930354A\r2:4B3132333435\r\r>'}))
        self.assertEqual(info['vin'], '1G4JC5D905JK12345')


@unittest.skipUnless(tools, 'Gateway dependency environment required')
class ObdBleToolTests(unittest.TestCase):
    def test_obd_reads_without_approval_in_one_exchange(self):
        calls = []

        def run(action, args=None, timeout=0, agent=None):
            calls.append((action, args))
            if action == 'ble-inspect':
                return {'name': 'OBDII', 'services': ADAPTER}
            return {'responses': answers('codes', {})}

        with patch('righaven.tools._pc', return_value=(None, None)), patch('righaven.host_bridge.run', side_effect=run):
            result = json.loads(tools.harness_bluetooth.func(runtime=None, address='66:1E:32:FA:3C:20', action='obd', request='codes'))
        self.assertEqual([c['code'] for c in result['stored']], ['P0133', 'P0171'])
        self.assertEqual([a for a, _ in calls], ['ble-inspect', 'ble-exchange'])
        args = calls[1][1]
        self.assertEqual((args['characteristic'], args['notify'], args['until']), ('0000fff2-0000-1000-8000-00805f9b34fb', '0000fff1-0000-1000-8000-00805f9b34fb', '3e'))
        self.assertNotIn(obd_ble.encode('03').replace('03', '04', 1), args['commands'].split(','))

    def test_old_agent_is_told_to_update(self):
        def run(action, args=None, timeout=0, agent=None):
            raise ValueError('Questa azione non è disponibile su questo agente')

        with patch('righaven.tools._pc', return_value=('a1', None)), patch('righaven.host_bridge.run', side_effect=run), \
                self.assertRaisesRegex(ValueError, 'too old'):
            tools.harness_bluetooth.func(runtime=None, address='66:1E:32:FA:3C:20', action='obd', service='fff0', characteristic='fff2', notify='fff1')

    def test_exchange_and_write_still_need_a_connection(self):
        with self.assertRaises(ValueError):
            tools.harness_bluetooth.func(runtime=None, address='66:1E:32:FA:3C:20', action='exchange', service='fff0', characteristic='fff2', value='30330d')


class HostBridgeExchangeTests(unittest.TestCase):
    def test_exchange_is_never_asked_from_the_page(self):
        self.assertIn('ble-exchange', host_bridge.APPROVED_ONLY)


if __name__ == '__main__':
    unittest.main()
