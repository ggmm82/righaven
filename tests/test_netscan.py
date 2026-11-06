"""netscan: the perimeter of the connection, approvals and nmap results."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import netscan_job  # noqa: E402
import netscan_tools  # noqa: E402
from extended_specs import TOOLS  # noqa: E402

XML = '''<?xml version="1.0"?><nmaprun>
<host><status state="up"/><address addr="192.168.1.20" addrtype="ipv4"/><hostnames><hostname name="nas.local"/></hostnames>
<ports><port protocol="tcp" portid="445"><state state="open"/><service name="microsoft-ds" product="Samba smbd" version="4.6"/>
<script id="smb-vuln-ms17-010" output="VULNERABLE: Remote Code Execution (CVE-2017-0143) Risk factor: HIGH CVSS: 9.3"/></port>
<port protocol="tcp" portid="22"><state state="closed"/><service name="ssh"/></port></ports></host>
<host><status state="down"/><address addr="192.168.1.21" addrtype="ipv4"/></host>
<host><status state="up"/><address addr="192.168.1.5" addrtype="ipv4"/><ports><port protocol="tcp" portid="1883"><state state="open"/><service name="mqtt"/></port></ports></host>
</nmaprun>'''


class NetscanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {'kind': 'network', 'ranges': ['192.168.1.0/24'], 'exclude': ['192.168.1.1/32'], 'write_enabled': True}

    def test_operations_and_bounded_schemas(self):
        self.assertEqual([t['name'] for t in TOOLS['netscan']], ['netscan.discover', 'netscan.services', 'netscan.vulnerabilities'])
        vulnerabilities = next(t for t in TOOLS['netscan'] if t['name'] == 'netscan.vulnerabilities')['inputSchema']
        self.assertEqual(vulnerabilities['properties']['profile']['enum'], ['safe', 'tls'], 'no intrusive profile exists')

    def test_targets_never_leave_the_authorized_networks(self):
        self.assertEqual(netscan_job.scope(self.cfg, {}), (['192.168.1.0/24'], ['192.168.1.1/32']))
        self.assertEqual(netscan_job.scope(self.cfg, {'targets': ['192.168.1.10']})[0], ['192.168.1.10/32'])
        for target in ('192.168.2.1', '192.168.0.0/16', '0.0.0.0/0'):
            with self.subTest(target=target), self.assertRaisesRegex(netscan_job.UserError, 'outside'):
                netscan_job.scope(self.cfg, {'targets': [target]})
            with self.subTest(adapter=target), self.assertRaisesRegex(ValueError, 'outside'):
                netscan_tools.inside([target], self.cfg)

    def test_vulnerability_scans_need_the_approved_scope_and_profile(self):
        with self.assertRaisesRegex(netscan_job.UserError, 'harness_device_change'):
            netscan_job.approved(self.cfg, ['192.168.1.10/32'], 'safe')
        cfg = {**self.cfg, 'approvals': [{'id': 's1', 'action': 'scan', 'fingerprint': netscan_job.scope_fingerprint(['192.168.1.10'], 'safe')}]}
        self.assertEqual(netscan_job.approved(cfg, ['192.168.1.10/32'], 'safe'), 's1')
        with self.assertRaises(netscan_job.UserError):
            netscan_job.approved(cfg, ['192.168.1.10/32'], 'tls')
        with self.assertRaises(netscan_job.UserError):
            netscan_job.approved(cfg, ['192.168.1.0/24'], 'safe')
        folder = self.root / 'connections'
        folder.mkdir()
        (folder / 'lan.json').write_text(json.dumps({**self.cfg, 'write_enabled': False}))
        with patch.object(netscan_tools, 'CONNECTIONS', folder), self.assertRaisesRegex(ValueError, 'not allowed'):
            netscan_tools.invoke('netscan', 'vulnerabilities', {'connection': 'lan', 'profile': 'safe', 'output': str(self.root / 'out')}, None)

    def test_nmap_results_become_inventory_map_and_findings(self):
        xml = self.root / 'scan.xml'
        xml.write_text(XML)
        hosts = netscan_job.parse(xml)
        self.assertEqual([h['address'] for h in hosts], ['192.168.1.5', '192.168.1.20'], 'down hosts and closed ports are left out')
        self.assertEqual(hosts[1]['ports'][0]['product'], 'Samba smbd 4.6')
        netscan_job.save_inventory(hosts, self.root, ['192.168.1.0/24'])
        self.assertIn('192.168.1.20,nas.local,445,tcp,microsoft-ds,Samba smbd 4.6', (self.root / 'inventory.csv').read_text())
        self.assertIn('N0 --- H192_168_1_20["192.168.1.20 nas.local<br/>445/microsoft-ds"]', (self.root / 'network-map.mmd').read_text())
        self.assertEqual(netscan_job.severity(hosts[1]['ports'][0]['scripts'][0]['output']), ('critical', 9.3))
        unsafe = self.root / 'unsafe.xml'
        unsafe.write_text('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><nmaprun>&e;</nmaprun>')
        with self.assertRaises(Exception):
            netscan_job.parse(unsafe)


if __name__ == '__main__':
    unittest.main()
