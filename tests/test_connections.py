"""User connections: encrypted at rest, public metadata only, delivered per assignment."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from righaven import connections, projects

ROOT = Path(__file__).resolve().parents[1]
PLAN = [{'id': 'schema', 'agent': 'dlt', 'goal': 'Leggi lo schema', 'depends_on': []}]


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        for p in (patch.object(connections, 'folder', side_effect=lambda user: (base / 'users' / str(user) / 'righaven-connections').mkdir(parents=True, exist_ok=True)
                               or base / 'users' / str(user) / 'righaven-connections'),
                  patch.dict(os.environ, {'RIGHAVEN_CREDENTIALS_KEY': Fernet.generate_key().decode()})):
            p.start();self.addCleanup(p.stop)
        self.workspace = base / 'conversation';self.workspace.mkdir()

    def sqlserver(self, **extra):
        return connections.save('alice', {'id': 'erp', 'kind': 'sqlserver', 'name': 'ERP', 'host': 'erp.example.com', 'database': 'Vendite',
                                          'username': 'lettore', 'password': 'p@ss:w/rd', 'read_only': True, **extra})

    def test_secrets_are_encrypted_and_never_returned(self):
        view = self.sqlserver()
        self.assertNotIn('password', view)
        self.assertTrue(view['has_secret'])
        stored = (connections.folder('alice') / 'erp.json').read_text()
        self.assertNotIn('p@ss:w/rd', stored)
        self.assertEqual(oct((connections.folder('alice') / 'erp.json').stat().st_mode & 0o777), '0o600')
        self.assertEqual([r['id'] for r in connections.listing('alice')], ['erp'])
        self.assertEqual(connections.listing('bob'), [], 'connections are personal')
        updated = connections.save('alice', {'kind': 'sqlserver', 'name': 'ERP lettura', 'host': 'erp.example.com', 'database': 'Vendite',
                                             'username': 'lettore', 'read_only': True}, 'erp')
        self.assertEqual(updated['name'], 'ERP lettura')
        self.assertEqual(connections._read('alice', 'erp')['password'], 'p@ss:w/rd', 'an empty password keeps the stored one')

    def test_validation(self):
        for body, message in (({'kind': 'db2', 'name': 'x'}, 'Tipo'), ({'id': 'A', 'kind': 'mysql', 'name': 'x'}, 'id'),
                              ({'id': 'pg', 'kind': 'postgres', 'name': 'x', 'host': 'db', 'database': 'd', 'username': 'u'}, 'Password'),
                              ({'id': 'pg', 'kind': 'postgres', 'name': 'x', 'host': 'db', 'port': 70000, 'database': 'd', 'username': 'u', 'password': 'p'}, 'Porta'),
                              ({'id': 'az', 'kind': 'entra', 'name': 'x', 'tenant_id': 'contoso.onmicrosoft.com', 'client_id': 'non-un-guid', 'client_secret': 's'}, 'client')):
            with self.assertRaisesRegex(ValueError, message):
                connections.save('alice', body)
        self.sqlserver()
        with self.assertRaisesRegex(ValueError, 'già'):
            self.sqlserver()

    def test_connection_files_for_each_engine(self):
        pg = connections._file(connections.validate({'id': 'pg', 'kind': 'postgres', 'name': 'x', 'host': 'pg.example.com', 'database': 'dw',
                                                     'username': 'u', 'password': 'p w', 'read_only': True}), 'alice')
        self.assertEqual(pg['url'], 'postgresql+psycopg://u:p%20w@pg.example.com:5432/dw?sslmode=require')
        my = connections._file(connections.validate({'id': 'my', 'kind': 'mysql', 'name': 'x', 'host': 'my.example.com', 'database': 'shop',
                                                     'username': 'u', 'password': 'p', 'read_only': True, 'tls': False}), 'alice')
        self.assertEqual(my['url'], 'mysql+pymysql://u:p@my.example.com:3306/shop')
        self.sqlserver()
        ms = connections._file(connections._read('alice', 'erp'), 'alice')
        self.assertEqual(ms['url'], 'mssql+pymssql://lettore:p%40ss%3Aw%2Frd@erp.example.com:1433/Vendite')
        self.assertTrue(ms['usql_url'].startswith('sqlserver://lettore:p%40ss%3Aw%2Frd@erp.example.com:1433?database=Vendite&encrypt=true'))
        self.assertIn('databaseName=Vendite', ms['jdbc_url'])
        connections.save('alice', {'id': 'azure', 'kind': 'entra', 'name': 'Tenant', 'tenant_id': 'contoso.onmicrosoft.com',
                                   'client_id': '11111111-2222-3333-4444-555555555555', 'client_secret': 'segreto'})
        connections.save('alice', {'id': 'fabric', 'kind': 'sqlserver', 'name': 'Fabric', 'host': 'abc.datawarehouse.fabric.microsoft.com',
                                   'database': 'wh', 'authentication': 'entra', 'entra_connection': 'azure', 'read_only': True})
        fabric = connections._file(connections._read('alice', 'fabric'), 'alice')
        self.assertTrue(fabric['usql_url'].startswith('azuresql://11111111-2222-3333-4444-555555555555%40contoso.onmicrosoft.com:segreto@'))
        self.assertIn('fedauth=ActiveDirectoryServicePrincipal', fabric['usql_url'])
        self.assertNotIn('url', fabric)
        self.assertEqual(connections.public_view(connections._read('alice', 'fabric'))['tools'], ['usql'])
        with self.assertRaisesRegex(ValueError, 'Usata'):
            connections.delete('alice', 'azure')

    def test_private_addresses_need_operator_consent(self):
        with self.assertRaisesRegex(ValueError, 'privato'):
            connections._addresses('localhost', 5432)
        with patch.dict(os.environ, {'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'}):
            self.assertTrue(connections._addresses('localhost', 5432))

    def test_assignment_and_per_assignment_delivery(self):
        self.sqlserver()
        connections.save('alice', {'id': 'scrittura', 'kind': 'postgres', 'name': 'DW', 'host': 'dw.example.com', 'database': 'dw',
                                   'username': 'u', 'password': 'p'})
        with self.assertRaisesRegex(ValueError, 'Avvia prima'):
            connections.assign('alice', self.workspace, ['erp'])
        projects.create_plan(self.workspace, 'Catalogo ERP', PLAN)
        assigned = connections.assign('alice', self.workspace, ['erp', 'scrittura'])
        self.assertEqual([c['id'] for c in assigned], ['erp', 'scrittura'])
        self.assertNotIn('p@ss:w/rd', json.dumps(projects.read_project(self.workspace)['connections']))
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-c')
        private = Path(self.temp.name) / 'job-c'
        self.assertEqual(sorted(p.name for p in private.iterdir()), ['erp.json', 'scrittura.json'], 'every assigned connection, chosen by the user')
        self.assertEqual(json.loads((private / 'erp.json').read_text())['username'], 'lettore')
        self.assertFalse(json.loads((private / 'scrittura.json').read_text())['read_only'], 'adapters refuse it, the delivery does not decide')
        self.assertEqual(delivery.mount_arguments(lambda path, target, ro: f'{path}:{target}:{ro}'), ['--mount', f'{private}:/run/righaven/connections:True'])
        self.assertEqual([c['id'] for c in delivery.public], ['erp', 'scrittura'])
        self.assertNotIn('p@ss:w/rd', json.dumps(delivery.public))
        delivery.close()
        self.assertFalse(private.exists(), 'the private folder disappears with the worker')
        connections.assign('alice', self.workspace, [])
        self.assertEqual(connections.Delivery(self.workspace, Path(self.temp.name) / 'job-d').mount_arguments(None), [], 'nothing when the user unticks them')

    def test_oracle_connection_file(self):
        ora = connections._file(connections.validate({'id': 'ora', 'kind': 'oracle', 'name': 'x', 'host': 'ora.example.com', 'database': 'ORCLPDB1',
                                                      'username': 'hr', 'password': 'p', 'read_only': True}), 'alice')
        self.assertEqual(ora['url'], 'oracle+oracledb://hr:p@ora.example.com:1521/?service_name=ORCLPDB1')
        self.assertEqual(ora['usql_url'], 'oracle://hr:p@ora.example.com:1521/ORCLPDB1')
        self.assertEqual(ora['jdbc_url'], 'jdbc:oracle:thin:@//ora.example.com:1521/ORCLPDB1')

    def test_data_adapters_read_the_delivered_file(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        import data_tools
        folder = Path(self.temp.name) / 'run'
        folder.mkdir()
        (folder / 'erp.json').write_text(json.dumps({'kind': 'sqlserver', 'read_only': True, 'url': 'mssql+pymssql://u:segreto@h:1433/d',
                                                     'usql_url': 'sqlserver://u:segreto@h:1433?database=d', 'username': 'u', 'password': 'segreto'}))
        real = data_tools.Path
        with patch.object(data_tools, 'Path', side_effect=lambda p, *a: folder if str(p) == '/run/righaven/connections' else real(p, *a)):
            cfg, values = data_tools.secret_config({'connection': 'erp'}, None, None)
        self.assertEqual(cfg['usql_url'], 'sqlserver://u:segreto@h:1433?database=d')
        self.assertIn('segreto', values, 'the password is redacted from native logs')
        (folder / 'scrittura.json').write_text(json.dumps({'kind': 'postgres', 'read_only': False, 'url': 'postgresql://u:p@h/d'}))
        with patch.object(data_tools, 'Path', side_effect=lambda p, *a: folder if str(p) == '/run/righaven/connections' else real(p, *a)):
            with self.assertRaisesRegex(ValueError, 'read-only'):
                data_tools.secret_config({'connection': 'scrittura'}, None, None)

    def test_ui_wiring(self):
        docker = (ROOT / 'docker/Dockerfile.frontend').read_text()
        self.assertIn('frontend/connections-page.tsx ./frontend/src/app/workspace/connections/page.tsx', docker)
        self.assertIn('frontend/project-connections.tsx', docker)
        self.assertIn('/workspace/connections', (ROOT / 'core/frontend/src/components/workspace/workspace-nav-chat-list.tsx').read_text())
        self.assertIn('<ProjectConnections', (ROOT / 'frontend/delegate-progress.tsx').read_text())


if __name__ == '__main__':
    unittest.main()
