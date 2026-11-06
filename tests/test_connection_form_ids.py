"""Short IDs are accepted, bad IDs and a missing local device are explained."""
import unittest
from unittest.mock import patch

from righaven import connections


class ConnectionFormTests(unittest.TestCase):
    def device(self, **extra):
        return {'kind': 'device', 'name': 'UsbRW', 'transport': 'local', 'access': 'write', 'baud': 115200, **extra}

    def test_one_letter_id_is_accepted(self):
        with patch.dict('os.environ', {'RIGHAVEN_DEVICES': '/dev/ttyUSB0'}):
            record = connections.validate(self.device(id='a', device='/dev/ttyUSB0'))
        self.assertEqual(record['id'], 'a')
        self.assertTrue(record['write_enabled'])

    def test_invalid_id_says_what_is_allowed(self):
        for bad in ('Usb', '1usb', 'usb rw', 'x' * 41, ''):
            with self.assertRaisesRegex(ValueError, 'lettere minuscole, cifre e trattini'):
                connections.validate(self.device(id=bad, device='/dev/ttyUSB0'))

    def test_missing_local_device_says_how_to_offer_it(self):
        with patch.dict('os.environ', {'RIGHAVEN_DEVICES': ''}):
            with self.assertRaisesRegex(ValueError, 'RigHaven.exe usb'):
                connections.validate(self.device(id='usb-rw'))


if __name__ == '__main__':
    unittest.main()
