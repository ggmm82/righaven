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
                              ({'id': 'az', 'kind': 'entra', 'mode': 'application', 'name': 'x', 'tenant_id': 'contoso.onmicrosoft.com', 'client_id': 'non-un-guid', 'client_secret': 's'}, 'client')):
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
        connections.save('alice', {'id': 'azure', 'kind': 'entra', 'mode': 'application', 'name': 'Tenant', 'tenant_id': 'contoso.onmicrosoft.com',
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

    def test_personal_microsoft_account_signs_in_with_device_code_and_delivers_only_access_tokens(self):
        import base64
        claims = base64.urlsafe_b64encode(json.dumps({'preferred_username': 'marco@contoso.com', 'name': 'Marco'}).encode()).decode().rstrip('=')
        calls = []

        def microsoft(url, data, timeout):
            calls.append((url, dict(data)))
            class Reply:
                headers = {'content-type': 'application/json'}
                def __init__(self, code, body): self.status_code, self.body = code, body
                def json(self): return self.body
            if url.endswith('/devicecode'):
                return Reply(200, {'device_code': 'DEVICE', 'user_code': 'ABCD-EFGH', 'verification_uri': 'https://microsoft.com/devicelogin', 'expires_in': 900, 'interval': 5})
            if data['grant_type'].endswith('device_code'):
                return Reply(400, {'error': 'authorization_pending'}) if len(calls) == 2 else Reply(200, {'refresh_token': 'RT-1', 'id_token': 'h.' + claims + '.s', 'access_token': 'x'})
            if data['refresh_token'] == 'RT-REVOKED':
                return Reply(400, {'error': 'invalid_grant', 'error_codes': [700082]})
            return Reply(200, {'access_token': 'AT-' + data['scope'].split('/')[2], 'refresh_token': 'RT-' + str(len(calls)), 'expires_in': 3600})

        view = connections.save('alice', {'id': 'mio', 'kind': 'entra', 'name': 'Il mio account'})
        self.assertEqual((view['mode'], view['tenant_id'], view['client_id'], view['signed_in']), ('user', 'organizations', connections.PUBLIC_CLIENT, False))
        connections.save('alice', {'id': 'azsql', 'kind': 'sqlserver', 'name': 'Azure SQL', 'host': 'srv.database.windows.net', 'database': 'vendite',
                                   'authentication': 'entra', 'entra_connection': 'mio', 'read_only': True})
        with patch('httpx.post', side_effect=microsoft):
            self.assertFalse(connections.test('alice', 'mio')['ok'], 'not signed in yet')
            started = connections.sign_in('alice', 'mio')
            self.assertEqual((started['user_code'], started['verification_uri']), ('ABCD-EFGH', 'https://microsoft.com/devicelogin'))
            self.assertIn('offline_access', calls[0][1]['scope'])
            self.assertEqual(connections.complete_sign_in('alice', 'mio')['status'], 'pending')
            self.assertEqual(connections.complete_sign_in('alice', 'mio'), {'status': 'signed_in', 'account': 'marco@contoso.com'})
            self.assertEqual(connections.complete_sign_in('alice', 'mio')['status'], 'expired', 'the device code is single use')
            stored = (connections.folder('alice') / 'mio.json').read_text()
            self.assertNotIn('RT-1', stored, 'refresh token encrypted at rest')
            public = connections.public_view(connections._read('alice', 'mio'))
            self.assertTrue(public['signed_in']); self.assertNotIn('refresh_token', public)
            self.assertEqual(public['account'], 'marco@contoso.com')
            self.assertTrue(connections.test('alice', 'mio')['ok'])
            sql = connections._file(connections._read('alice', 'azsql'), 'alice')
            self.assertIn('fedauth=ActiveDirectoryServicePrincipalAccessToken', sql['usql_url'])
            self.assertIn(':AT-database.windows.net@srv.database.windows.net:1433', sql['usql_url'])
            identity = connections._file(connections._read('alice', 'mio'), 'alice')
            self.assertEqual((identity['access_token'], identity['fabric_access_token']), ('AT-database.windows.net', 'AT-api.fabric.microsoft.com'))
            self.assertNotIn('refresh_token', json.dumps([sql, identity]), 'workers never receive the refresh token')
            self.assertNotEqual(connections._read('alice', 'mio')['refresh_token'], 'RT-1', 'rotated refresh tokens are kept')
            connections.save('alice', {'kind': 'entra', 'name': 'Il mio account', 'tenant_id': 'contoso.onmicrosoft.com'}, 'mio')
            self.assertFalse(connections.public_view(connections._read('alice', 'mio'))['signed_in'], 'another tenant needs a new sign-in')
            record = connections._read('alice', 'mio'); connections._write('alice', {**record, 'refresh_token': 'RT-REVOKED'})
            with self.assertRaisesRegex(ValueError, 'sign in again'):
                connections._file(connections._read('alice', 'azsql'), 'alice')
            self.assertIn('AADSTS700082', connections.test('alice', 'mio')['detail'])
            self.assertFalse(connections.sign_out('alice', 'mio')['signed_in'])
        with self.assertRaisesRegex(ValueError, 'personal'):
            connections.sign_in('alice', 'azsql')

    def test_pasted_urls_and_connection_strings_fill_server_port_database_and_user(self):
        cases = {
            'Server=tcp:vendite.database.windows.net,1433;Initial Catalog=erp;User ID=marco@contoso.com;Encrypt=True;':
                {'host': 'vendite.database.windows.net', 'port': 1433, 'database': 'erp', 'username': 'marco@contoso.com'},
            'jdbc:sqlserver://srv.example.com:1444;databaseName=dw;user=lettore;encrypt=true':
                {'host': 'srv.example.com', 'port': 1444, 'database': 'dw', 'username': 'lettore'},
            'tcp:abc.datawarehouse.fabric.microsoft.com,1433': {'host': 'abc.datawarehouse.fabric.microsoft.com', 'port': 1433},
            'postgresql://lettore@pg.example.com:5433/vendite?sslmode=require': {'host': 'pg.example.com', 'port': 5433, 'database': 'vendite', 'username': 'lettore'},
            'https://vendite.database.windows.net/': {'host': 'vendite.database.windows.net'},
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(connections.address('sqlserver', text, {'port': 1433}), expected)
        self.assertEqual(connections.address('sqlserver', 'db.example.com'), {}, 'a plain host is left as typed')
        for wrong in ('Server=;Database=x;', 'tcp:srv\\SQLEXPRESS'):
            with self.assertRaises(ValueError):
                connections.address('sqlserver', wrong)
        view = connections.save('alice', {'id': 'incollata', 'kind': 'sqlserver', 'name': 'ERP', 'password': 'p', 'read_only': True,
                                          'host': 'Server=tcp:erp.example.com,1444;Database=Vendite;User ID=lettore;'})
        self.assertEqual((view['host'], view['port'], view['database'], view['username']), ('erp.example.com', 1444, 'Vendite', 'lettore'))

    def test_sql_server_with_my_microsoft_account_user_and_database_list(self):
        import base64
        claims = lambda who: base64.urlsafe_b64encode(json.dumps({'preferred_username': who}).encode()).decode().rstrip('=')
        signed_as = ['altro@contoso.com', 'marco@contoso.com']

        class Reply:
            headers = {'content-type': 'application/json'}
            def __init__(self, code, body): self.status_code, self.body = code, body
            def json(self): return self.body

        def post(url, data, timeout):
            if url.endswith('/devicecode'):
                return Reply(200, {'device_code': 'D', 'user_code': 'C', 'verification_uri': 'https://microsoft.com/devicelogin'})
            if data['grant_type'].endswith('device_code'):
                return Reply(200, {'refresh_token': 'RT', 'id_token': 'h.' + claims(signed_as.pop(0)) + '.s'})
            return Reply(200, {'access_token': 'AT ' + data['scope'].split()[0], 'expires_in': 3600})

        def get(url, headers, timeout):
            self.assertTrue(headers['Authorization'].startswith('Bearer AT '))
            if url.endswith('/subscriptions?api-version=2022-12-01'):
                return Reply(200, {'value': [{'subscriptionId': 's1', 'displayName': 'Produzione'}, {'subscriptionId': 's2', 'displayName': 'Altra'}]})
            if '/subscriptions/s2/' in url:
                return Reply(403, {'error': {'code': 'AuthorizationFailed'}})
            if '/subscriptions/s1/resources' in url:
                self.assertIn("Microsoft.Sql/servers/databases", url)
                return Reply(200, {'value': [{'name': 'vendite/master'}, {'name': 'vendite/erp', 'location': 'westeurope'},
                                             {'name': 'altro/hr', 'location': 'westeurope'}]})
            if url.endswith('/v1/workspaces'):
                return Reply(200, {'value': [{'id': 'w1', 'displayName': 'Analisi'}]})
            if url.endswith('/w1/warehouses'):
                return Reply(200, {'value': [{'displayName': 'Magazzino', 'properties': {'connectionString': 'abc.datawarehouse.fabric.microsoft.com'}}]})
            if url.endswith('/w1/lakehouses'):
                return Reply(200, {'value': [{'displayName': 'Lago', 'properties': {'sqlEndpointProperties': {'connectionString': 'other.datawarehouse.fabric.microsoft.com'}}}]})
            return Reply(404, {'errorCode': 'NotFound'})

        view = connections.save('alice', {'id': 'azsql', 'kind': 'sqlserver', 'name': 'Azure SQL', 'authentication': 'microsoft', 'read_only': True,
                                          'host': 'Server=tcp:vendite.database.windows.net,1433;User ID=marco@contoso.com;'})
        self.assertEqual((view['username'], view['database'], view['signed_in'], view['tools']), ('marco@contoso.com', '', False, ['usql']))
        with self.assertRaisesRegex(ValueError, 'email'):
            connections.save('alice', {'id': 'senza-email', 'kind': 'sqlserver', 'name': 'x', 'authentication': 'microsoft', 'host': 'a.database.windows.net', 'username': 'marco'})
        with patch('httpx.post', side_effect=post), patch('httpx.get', side_effect=get):
            connections.sign_in('alice', 'azsql')
            wrong = connections.complete_sign_in('alice', 'azsql')
            self.assertEqual(wrong['status'], 'failed'); self.assertIn('altro@contoso.com', wrong['detail'])
            self.assertFalse(connections.public_view(connections._read('alice', 'azsql'))['signed_in'], 'another account is not kept')
            connections.sign_in('alice', 'azsql')
            self.assertEqual(connections.complete_sign_in('alice', 'azsql')['status'], 'signed_in')
            listed = connections.databases('alice', 'azsql')
            self.assertEqual(listed, {'databases': [{'name': 'erp', 'detail': 'Produzione · westeurope'}], 'source': 'azure'})
            with self.assertRaisesRegex(ValueError, 'Choose the database'):
                connections._file(connections._read('alice', 'azsql'), 'alice')
            body = {'kind': 'sqlserver', 'name': 'Azure SQL', 'authentication': 'microsoft', 'read_only': True,
                    'host': 'vendite.database.windows.net', 'username': 'marco@contoso.com', 'database': 'erp'}
            self.assertTrue(connections.save('alice', body, 'azsql')['signed_in'], 'choosing the database keeps the sign-in')
            delivered = connections._file(connections._read('alice', 'azsql'), 'alice')
            self.assertTrue(delivered['usql_url'].startswith('azuresql://marco%40contoso.com:AT%20https%3A%2F%2Fdatabase.windows.net%2F.default@vendite.database.windows.net:1433?database=erp'))
            self.assertNotIn('RT', json.dumps(delivered))
            connections.save('alice', {**body, 'id': 'fabric', 'host': 'abc.datawarehouse.fabric.microsoft.com', 'database': ''})
            connections._write('alice', {**connections._read('alice', 'fabric'), 'refresh_token': 'RT'})
            self.assertEqual(connections.databases('alice', 'fabric')['databases'], [{'name': 'Magazzino', 'detail': 'Warehouse · Analisi'}])
            connections.save('alice', {**body, 'id': 'onprem', 'host': 'sql.example.com'})
            connections._write('alice', {**connections._read('alice', 'onprem'), 'refresh_token': 'RT'})
            with self.assertRaisesRegex(ValueError, 'type the database name'):
                connections.databases('alice', 'onprem')
        self.sqlserver()
        with self.assertRaisesRegex(ValueError, 'Microsoft account'):
            connections.databases('alice', 'erp')

    def test_existing_entra_applications_keep_working(self):
        connections.save('alice', {'id': 'app', 'kind': 'entra', 'mode': 'application', 'name': 'App', 'tenant_id': 'contoso.onmicrosoft.com',
                                   'client_id': '11111111-2222-3333-4444-555555555555', 'client_secret': 'segreto'})
        record = connections._read('alice', 'app'); record.pop('mode'); connections._write('alice', record)
        self.assertEqual(connections.public_view(connections._read('alice', 'app'))['mode'], 'application')
        with self.assertRaisesRegex(ValueError, 'Segreto'):
            connections.save('alice', {'id': 'app2', 'kind': 'entra', 'mode': 'application', 'name': 'App', 'tenant_id': 'contoso.onmicrosoft.com',
                                       'client_id': '11111111-2222-3333-4444-555555555555'})

    def test_private_addresses_need_operator_consent(self):
        with self.assertRaisesRegex(ValueError, 'privato'):
            connections._addresses('localhost', 5432)
        with patch.dict(os.environ, {'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'}):
            self.assertTrue(connections._addresses('localhost', 5432))

    def test_assignment_and_per_assignment_delivery(self):
        self.sqlserver()
        connections.save('alice', {'id': 'scrittura', 'kind': 'postgres', 'name': 'DW', 'host': 'dw.example.com', 'database': 'dw',
                                   'username': 'u', 'password': 'p'})
        chosen = connections.assign('alice', self.workspace, ['erp'])
        self.assertEqual([c['id'] for c in chosen], ['erp'])
        self.assertIsNone(projects.read_project(self.workspace))
        projects.create_plan(self.workspace, 'Catalogo ERP', PLAN)
        self.assertEqual([c['id'] for c in projects.read_project(self.workspace)['connections']], ['erp'])
        assigned = connections.assign('alice', self.workspace, ['erp', 'scrittura'])
        self.assertEqual([c['id'] for c in assigned], ['erp', 'scrittura'])
        self.assertNotIn('p@ss:w/rd', json.dumps(projects.read_project(self.workspace)['connections']))
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-c', role={'connections':['erp','scrittura']})
        private = Path(self.temp.name) / 'job-c'
        self.assertEqual(sorted(p.name for p in private.iterdir()), ['erp.json', 'scrittura.json'], 'every assigned connection, chosen by the user')
        self.assertEqual(json.loads((private / 'erp.json').read_text())['username'], 'lettore')
        self.assertFalse(json.loads((private / 'scrittura.json').read_text())['read_only'], 'adapters refuse it, the delivery does not decide')
        self.assertEqual(delivery.mount_arguments(lambda path, target, ro: f'{path}:{target}:{ro}'), ['--mount', f'{private}:/run/righaven/connections:True'])
        self.assertEqual([c['id'] for c in delivery.public], ['erp', 'scrittura'])
        self.assertNotIn('p@ss:w/rd', json.dumps(delivery.public))
        self.assertEqual(connections.Delivery(self.workspace, Path(self.temp.name)/'review').public, [], 'review roles receive no connections by default')
        with self.assertRaises(ValueError):connections.Delivery(self.workspace, Path(self.temp.name)/'denied', role={'connections':['not-granted']})
        delivery.close()
        self.assertFalse(private.exists(), 'the private folder disappears with the worker')
        connections.assign('alice', self.workspace, [])
        self.assertEqual(connections.Delivery(self.workspace, Path(self.temp.name) / 'job-d').mount_arguments(None), [], 'nothing when the user unticks them')

    def test_writing_needs_a_dedicated_schema_and_the_owner_consent_for_each_task(self):
        with self.assertRaisesRegex(ValueError, 'schema'):
            connections.save('alice', {'id': 'dw', 'kind': 'postgres', 'name': 'DW', 'host': 'dw.example.com', 'database': 'dw',
                                       'username': 'u', 'password': 'p', 'access': 'write'})
        view = connections.save('alice', {'id': 'dw', 'kind': 'postgres', 'name': 'DW', 'host': 'dw.example.com', 'database': 'dw',
                                          'username': 'u', 'password': 'p', 'access': 'write', 'write_schema': 'righaven', 'read_only': True})
        self.assertEqual((view['write_enabled'], view['write_schema'], view['read_only']), (True, 'righaven', False))
        self.sqlserver()
        projects.create_plan(self.workspace, 'Carico i mart', PLAN)
        with self.assertRaisesRegex(ValueError, 'Writing is not enabled'):
            connections.assign('alice', self.workspace, ['erp', 'dw'], ['erp'])
        with self.assertRaisesRegex(ValueError, 'assigned to the task'):
            connections.assign('alice', self.workspace, ['erp'], ['dw'])
        read_only = connections.assign('alice', self.workspace, ['erp', 'dw'])
        self.assertNotIn('write', read_only[1], 'assigned without consent: read access only')
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-r', role={'id': 'loader', 'connections': ['dw']})
        self.assertFalse(json.loads((Path(self.temp.name) / 'job-r' / 'dw.json').read_text())['write_enabled'])
        delivery.close()
        allowed = connections.assign('alice', self.workspace, ['erp', 'dw'], ['dw'])
        self.assertEqual((allowed[1]['write'], allowed[1]['write_schema']), (True, 'righaven'))
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-w', role={'id': 'loader', 'connections': ['dw']})
        delivered = json.loads((Path(self.temp.name) / 'job-w' / 'dw.json').read_text())
        self.assertEqual((delivered['write_enabled'], delivered['write_schema']), (True, 'righaven'))
        delivery.close()
        from righaven.audit_log import page
        self.assertIn('Accesso in scrittura consegnato a un incarico', [e['operation'] for e in page(self.workspace)['events']])

    def test_device_connections_validate_each_transport(self):
        view = connections.save('alice', {'id': 'sensori', 'kind': 'device', 'name': 'Sensori', 'transport': 'network', 'protocol': 'mqtt',
                                          'host': 'broker.example.com', 'tls': False, 'username': 'lettore', 'password': 'Mqtt.2026'})
        self.assertEqual((view['port'], view['topic'], view['tools'], view['read_only'], view['write_enabled']), (1883, '#', ['iot'], True, False))
        self.assertNotIn('password', view)
        again = connections.save('alice', {'kind': 'device', 'name': 'Sensori', 'transport': 'network', 'protocol': 'mqtt',
                                           'host': 'broker.example.com', 'tls': True, 'username': 'lettore', 'topic': 'city/+/bus'}, 'sensori')
        self.assertEqual((again['port'], again['topic']), (8883, 'city/+/bus'))
        self.assertEqual(connections.device_file(connections._read('alice', 'sensori'))['password'], 'Mqtt.2026', 'an empty password keeps the stored one')
        plc = connections.save('alice', {'id': 'plc', 'kind': 'device', 'name': 'PLC', 'transport': 'network', 'protocol': 'modbus-tcp',
                                         'host': 'plc.example.com', 'tls': False, 'unit': 3, 'access': 'write'})
        self.assertEqual((plc['port'], plc['unit'], plc['write_enabled']), (502, 3, True))
        serial = connections.save('alice', {'id': 'esp', 'kind': 'device', 'name': 'ESP32', 'transport': 'serial', 'host': 'ser2net.example.com', 'port': 4000})
        self.assertEqual((serial['protocol'], serial['baud']), ('rfc2217', 115200))
        self.assertEqual(connections.device_file(connections._read('alice', 'esp'))['url'], 'rfc2217://ser2net.example.com:4000')
        for bad in ({'transport': 'bluetooth'}, {'protocol': 'coap', 'host': 'x.example.com'}, {'protocol': 'modbus-tcp', 'host': 'x.example.com', 'unit': 300},
                    {'transport': 'serial', 'host': 'x.example.com', 'port': 4000, 'baud': 1234}, {'transport': 'serial', 'host': 'x.example.com'},
                    {'transport': 'local', 'device': '/dev/sda'}, {'transport': 'local', 'device': '/dev/ttyUSB0'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                connections.save('alice', {'id': 'bad', 'kind': 'device', 'name': 'Bad', **bad})
        with patch.dict(os.environ, {'RIGHAVEN_DEVICES': '/dev/ttyUSB0, /dev/sda, /dev/ttyACM1'}):
            self.assertEqual(connections.local_devices(), ['/dev/ttyUSB0', '/dev/ttyACM1'], 'only device classes for interfaces are offered')
            local = connections.save('alice', {'id': 'usb', 'kind': 'device', 'name': 'USB', 'transport': 'local', 'device': '/dev/ttyUSB0', 'baud': 9600})
            self.assertEqual((local['device'], local['baud']), ('/dev/ttyUSB0', 9600))
            self.assertTrue(connections.test('alice', 'usb')['ok'])
        self.assertFalse(connections.test('alice', 'usb')['ok'], 'withdrawn by the administrator')

    def test_devices_reach_only_the_container_of_the_task_and_read_only_without_consent(self):
        with patch.dict(os.environ, {'RIGHAVEN_DEVICES': '/dev/ttyUSB0'}):
            connections.save('alice', {'id': 'usb', 'kind': 'device', 'name': 'USB', 'transport': 'local', 'device': '/dev/ttyUSB0', 'access': 'write'})
            connections.save('alice', {'id': 'sensori', 'kind': 'device', 'name': 'Sensori', 'transport': 'network', 'protocol': 'http',
                                       'host': 'meter.example.com', 'tls': True, 'path': '/api/status'})
            projects.create_plan(self.workspace, 'Monitoraggio', PLAN)
            connections.assign('alice', self.workspace, ['usb', 'sensori'])
            role = {'id': 'monitor', 'connections': ['usb', 'sensori']}
            delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-r', role=role)
            arguments = delivery.mount_arguments(lambda path, target, ro: f'{path}:{target}:{ro}')
            self.assertIn('/dev/ttyUSB0:/dev/ttyUSB0:r', arguments, 'read-only device node without write consent')
            self.assertEqual(delivery.domains, ['meter.example.com'])
            files = Path(self.temp.name) / 'job-r'
            self.assertEqual(json.loads((files / 'sensori.json').read_text())['url'], 'https://meter.example.com:443/api/status')
            self.assertFalse(json.loads((files / 'usb.json').read_text())['write_enabled'])
            delivery.close()
            connections.assign('alice', self.workspace, ['usb', 'sensori'], ['usb'])
            delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-w', role=role)
            self.assertIn('/dev/ttyUSB0:/dev/ttyUSB0:rw', delivery.mount_arguments(lambda path, target, ro: path))
            delivery.close()
            self.assertEqual(connections.Delivery(self.workspace, Path(self.temp.name) / 'job-n', role={'id': 'review'}).mount_arguments(None), [],
                             'roles that do not declare the device do not get it')
        with self.assertRaisesRegex(ValueError, 'RIGHAVEN_DEVICES'):
            connections.Delivery(self.workspace, Path(self.temp.name) / 'job-x', role=role)
        from righaven.audit_log import page
        self.assertIn('Dispositivo consegnato a un incarico', [e['operation'] for e in page(self.workspace)['events']])

    def test_each_write_to_a_device_needs_the_owner_approval_of_that_exact_change(self):
        from righaven import device_changes
        connections.save('alice', {'id': 'tv', 'kind': 'device', 'name': 'TV sala', 'transport': 'network', 'protocol': 'adb',
                                   'host': 'tv.example.com', 'access': 'write'})
        key = connections._read('alice', 'tv')['adb_key']
        self.assertIn('BEGIN RSA PRIVATE KEY', key)
        self.assertEqual(connections._read('alice', 'tv')['adb_key'] if connections.save('alice', {'kind': 'device', 'name': 'TV', 'transport': 'network',
                         'protocol': 'adb', 'host': 'tv.example.com', 'access': 'write'}, 'tv') else '', key, 'the device authorizes one key, kept across edits')
        self.assertNotIn(key, (connections.folder('alice') / 'tv.json').read_text(), 'the key is encrypted at rest')
        projects.create_plan(self.workspace, 'TV', PLAN)
        connections.assign('alice', self.workspace, ['tv'])
        with self.assertRaisesRegex(ValueError, 'not allowed writing'):
            device_changes.request(self.workspace, 'tv', 'disable', package='com.vendor.ads')
        connections.assign('alice', self.workspace, ['tv'], ['tv'])
        apk = self.workspace / 'outputs' / 'app.apk'
        apk.parent.mkdir()
        apk.write_bytes(b'apk-v1')
        for bad in ({'action': 'format'}, {'action': 'install', 'file_path': '../../etc/passwd'}, {'action': 'install', 'file_path': '/mnt/user-data/outputs/missing.apk'},
                    {'action': 'disable', 'package': 'not a package'}, {'action': 'reboot', 'mode': 'factory'}, {'action': 'flash', 'file_path': 'outputs/app.apk'},
                    {'action': 'send', 'command': {'rm': '-rf'}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                device_changes.request(self.workspace, 'tv', **bad)
        install = device_changes.request(self.workspace, 'tv', 'install', file_path='/mnt/user-data/outputs/app.apk', note='Aggiorna l’app')
        self.assertEqual((install['status'], install['file']), ('pending', 'app.apk'))
        disable = device_changes.request(self.workspace, 'tv', 'disable', package='com.vendor.ads')
        role = {'id': 'tecnico', 'connections': ['tv']}
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-0', role=role)
        self.assertEqual(json.loads((Path(self.temp.name) / 'job-0' / 'tv.json').read_text())['approvals'], [], 'pending is not approved')
        delivery.close()
        apk.write_bytes(b'apk-v2')
        with self.assertRaisesRegex(ValueError, 'changed after the request'):
            device_changes.decide(self.workspace, install['id'], 'approve')
        device_changes.decide(self.workspace, disable['id'], 'approve')
        with self.assertRaisesRegex(ValueError, 'already decided'):
            device_changes.decide(self.workspace, disable['id'], 'reject')
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-1', role=role)
        delivered = json.loads((Path(self.temp.name) / 'job-1' / 'tv.json').read_text())
        self.assertEqual(delivered['approvals'], [{'id': disable['id'], 'action': 'disable', 'package': 'com.vendor.ads'}])
        self.assertEqual(delivered['adb_key'], key)
        delivery.close()
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-2', role=role)
        self.assertEqual(json.loads((Path(self.temp.name) / 'job-2' / 'tv.json').read_text())['approvals'], [], 'an approval is delivered once')
        delivery.close()
        statuses = {c['id']: c['status'] for c in device_changes.listing(self.workspace)}
        self.assertEqual(statuses, {install['id']: 'rejected', disable['id']: 'delivered'})
        command = device_changes.request(self.workspace, 'tv', 'send', command={'topic': 'x', 'payload': 'on', 'encoding': 'text'})
        self.assertEqual(command['command'], {'topic': 'x', 'payload': 'on', 'encoding': 'text'})
        from righaven.audit_log import page
        operations = [e['operation'] for e in page(self.workspace)['events']]
        self.assertIn('Riprogrammazione richiesta al proprietario', operations)
        self.assertIn('Riprogrammazione approvata', operations)

    def test_networks_to_map_need_authorization_and_scans_need_approval_of_the_exact_scope(self):
        from righaven import device_changes
        body = {'id': 'lan', 'kind': 'network', 'name': 'Rete di casa', 'ranges': ['192.168.1.0/24'], 'exclude': ['192.168.1.1'], 'authorized': True}
        with self.assertRaisesRegex(ValueError, 'written authorization'):
            connections.save('alice', {**body, 'authorized': False})
        with self.assertRaisesRegex(ValueError, 'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS'):
            connections.save('alice', body)
        with patch.dict(os.environ, {'RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS': 'allow'}):
            for bad in ({'ranges': ['8.8.8.0/24']}, {'ranges': ['10.0.0.0/8']}, {'ranges': ['not-a-net']}, {'ranges': []}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    connections.save('alice', {**body, **bad})
            view = connections.save('alice', {**body, 'access': 'write'})
            self.assertEqual((view['ranges'], view['exclude'], view['tools'], view['write_enabled']), (['192.168.1.0/24'], ['192.168.1.1/32'], ['netscan'], True))
            with patch.dict(os.environ, {'RIGHAVEN_SCAN_PUBLIC_TARGETS': 'allow'}):
                self.assertEqual(connections.save('alice', {**body, 'id': 'dmz', 'ranges': '203.0.113.0/28'})['ranges'], ['203.0.113.0/28'])
        projects.create_plan(self.workspace, 'Rete', PLAN)
        connections.assign('alice', self.workspace, ['lan'])
        role = {'id': 'analista', 'connections': ['lan']}
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-map', role=role)
        delivered = json.loads((Path(self.temp.name) / 'job-map' / 'lan.json').read_text())
        self.assertEqual((delivered['ranges'], delivered['write_enabled'], 'approvals' in delivered), (['192.168.1.0/24'], False, False), 'mapping only')
        delivery.close()
        with self.assertRaisesRegex(ValueError, 'not allowed writing'):
            device_changes.request(self.workspace, 'lan', 'scan', targets=['192.168.1.10'], profile='safe')
        connections.assign('alice', self.workspace, ['lan'], ['lan'])
        for bad in ({'targets': ['10.1.1.1'], 'profile': 'safe'}, {'targets': ['192.168.1.10'], 'profile': 'exploit'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                device_changes.request(self.workspace, 'lan', 'scan', **bad)
        with self.assertRaises(ValueError):
            device_changes.request(self.workspace, 'lan', 'send', command={'payload': 'x'})
        scan = device_changes.request(self.workspace, 'lan', 'scan', targets=['192.168.1.10', '192.168.1.0/28'], profile='safe', note='Servizi esposti')
        self.assertEqual(scan['command'], {'targets': ['192.168.1.10/32', '192.168.1.0/28'], 'profile': 'safe', 'exclude': ['192.168.1.1/32']})
        device_changes.decide(self.workspace, scan['id'], 'approve')
        delivery = connections.Delivery(self.workspace, Path(self.temp.name) / 'job-scan', role=role)
        approvals = json.loads((Path(self.temp.name) / 'job-scan' / 'lan.json').read_text())['approvals']
        delivery.close()
        sys.path.insert(0, str(ROOT / 'scripts'))
        import netscan_job
        self.assertEqual(approvals[0]['fingerprint'], netscan_job.scope_fingerprint(['192.168.1.0/28', '192.168.1.10'], 'safe'), 'gateway and worker agree on the scope')

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


    def test_destination_deferral_preserves_owner_usage_and_is_never_a_fake_write(self):
        connections.save('alice',{'id':'target','name':'Target','kind':'postgres','host':'db.example','database':'warehouse',
                                  'username':'writer','password':'fixture-only','access':'write','write_schema':'analytics'})
        projects.create_plan(self.workspace,'Write to the chosen destination',PLAN)
        connections.assign('alice',self.workspace,['target'],['target'])
        path=self.workspace/'.righaven-project/project.json';value=json.loads(path.read_text())
        value['connections']['uses']={'target':'destination'};connections.state.atomic_json(path,value)
        pending=connections.assign('alice',self.workspace,['target'],['target'])
        self.assertEqual(pending[0]['fulfillment'],'pending')
        postponed=connections.assign('alice',self.workspace,['target'],['target'],['target'])
        self.assertEqual(postponed[0]['fulfillment'],'deferred')
        self.assertEqual(json.loads(path.read_text())['connections']['uses'],{'target':'destination'})
        value=json.loads(path.read_text());value['status']='ready';connections.state.atomic_json(path,value)
        resumed=connections.assign('alice',self.workspace,['target'],['target'],[])
        self.assertEqual(resumed[0]['fulfillment'],'pending')
        self.assertEqual(json.loads(path.read_text())['status'],'blocked','removing deferral must reopen the unmet destination')
        with self.assertRaises(ValueError):connections.assign('alice',self.workspace,['target'],[],['target'])
        self.assertNotIn('fixture-only',json.dumps(resumed))

    def test_a_deleted_assigned_connection_fails_instead_of_silently_delivering_no_access(self):
        self.sqlserver();projects.create_plan(self.workspace,'Read the authorized source',PLAN)
        connections.assign('alice',self.workspace,['erp'])
        connections._path('alice','erp').unlink()
        with self.assertRaisesRegex(ValueError,'Assigned connection is unavailable'):
            connections.Delivery(self.workspace,self.workspace/'temporary-credentials',role={'connections':['erp']})
        self.assertFalse((self.workspace/'temporary-credentials').exists())


    def test_devices_next_to_an_agent_reach_workers_through_a_tunnel(self):
        from righaven import agents
        with patch.object(agents, 'owned', side_effect=lambda user, agent: {'id': agent} if user == 'alice' else (_ for _ in ()).throw(ValueError('Agente non trovato'))):
            com = connections.save('alice', {'id': 'obd', 'kind': 'device', 'name': 'OBD', 'transport': 'agent', 'agent': 'ag_0123456789ab', 'device': 'com5', 'baud': 38400})
            home = connections.save('alice', {'id': 'presa', 'kind': 'device', 'name': 'Presa', 'transport': 'agent', 'agent': 'ag_0123456789ab',
                                              'host': '192.168.1.44', 'protocol': 'http'})
            with self.assertRaises(ValueError):
                connections.save('bob', {'id': 'x', 'kind': 'device', 'name': 'X', 'transport': 'agent', 'agent': 'ag_0123456789ab', 'device': 'COM5'})
            with self.assertRaises(ValueError):
                connections.save('alice', {'id': 'y', 'kind': 'device', 'name': 'Y', 'transport': 'agent', 'agent': 'ag_0123456789ab', 'host': '8.8.8.8', 'protocol': 'http'})
        self.assertEqual((com['device'], home['port']), ('COM5', 80))
        record = connections._read('alice', 'obd')
        with patch('righaven.agent_hub.tunnel', return_value=('172.18.0.5', 42000)) as tunnel:
            serial = connections.through_agent(record)
            network = connections.through_agent(connections._read('alice', 'presa'))
        tunnel.assert_any_call('ag_0123456789ab', 'com:COM5')
        tunnel.assert_any_call('ag_0123456789ab', 'tcp:192.168.1.44:80')
        self.assertEqual(connections.device_file(serial)['url'], 'socket://172.18.0.5:42000')
        self.assertEqual(connections.device_file(network)['url'], 'http://172.18.0.5:42000/')
    def test_on_premise_databases_go_through_the_owners_agent(self):
        from righaven import agents
        owned = patch.object(agents, 'owned', side_effect=lambda user, agent: {'id': agent} if user == 'alice' else (_ for _ in ()).throw(ValueError('Agente non trovato')))
        with owned:
            sql = connections.save('alice', {'id': 'erp', 'kind': 'sqlserver', 'name': 'ERP', 'host': 'sql01.office.local', 'database': 'erp',
                                             'username': 'reader', 'password': 'secret-1', 'agent': 'ag_0123456789ab'})
            pg = connections.save('alice', {'id': 'mag', 'kind': 'postgres', 'name': 'Magazzino', 'host': '192.168.10.20', 'database': 'mag',
                                            'username': 'reader', 'password': 'secret-2', 'agent': 'ag_0123456789ab'})
            for wrong in ({'host': '8.8.8.8'}, {'host': '127.0.0.1'}, {'authentication': 'microsoft', 'username': 'a@b.com'}):
                with self.assertRaises(ValueError):
                    connections.save('alice', {'id': 'z', 'kind': 'sqlserver', 'name': 'Z', 'host': '10.0.0.4', 'database': 'z',
                                               'username': 'u', 'password': 'p', 'agent': 'ag_0123456789ab', **wrong})
            with self.assertRaises(ValueError):
                connections.save('bob', {'id': 'z', 'kind': 'postgres', 'name': 'Z', 'host': '10.0.0.4', 'database': 'z',
                                         'username': 'u', 'password': 'p', 'agent': 'ag_0123456789ab'})
            # Back to "from this server": the agent is removed, the stored password kept.
            moved = connections.save('alice', {'kind': 'postgres', 'name': 'Magazzino', 'host': 'db.example.org', 'database': 'mag',
                                               'username': 'reader', 'agent': ''}, 'mag')
        self.assertEqual((sql['agent'], sql['port'], pg['agent']), ('ag_0123456789ab', 1433, 'ag_0123456789ab'))
        self.assertNotIn('agent', moved)
        self.assertEqual(connections._read('alice', 'mag')['password'], 'secret-2')
        with patch('righaven.agent_hub.tunnel', return_value=('172.18.0.5', 42001)) as tunnel:
            record = connections.through_agent(connections._read('alice', 'erp'))
        tunnel.assert_called_once_with('ag_0123456789ab', 'tcp:sql01.office.local:1433')
        content = connections._file(record, 'alice')
        self.assertEqual((content['host'], content['port'], content['on_premise']), ('172.18.0.5', 42001, 'sql01.office.local'))
        self.assertIn('hostNameInCertificate=sql01.office.local', content['jdbc_url'])
        self.assertIn('&hostNameInCertificate=sql01.office.local', content['usql_url'])
        self.assertIn('@172.18.0.5:42001', content['url'])

    def test_the_test_of_an_on_premise_database_runs_on_the_agents_pc(self):
        from righaven import agent_hub, agents, host_bridge
        with patch.object(agents, 'owned', return_value={}):
            connections.save('alice', {'id': 'erp', 'kind': 'mysql', 'name': 'ERP', 'host': 'db01', 'database': 'erp',
                                       'username': 'reader', 'password': 'secret-1', 'agent': 'ag_0123456789ab'})
        with patch.object(agent_hub, 'online', return_value=False):
            self.assertFalse(connections.test('alice', 'erp')['ok'])
        with patch.object(agent_hub, 'online', return_value=True), patch.object(agent_hub, 'state', return_value={'actions': ['tcp-check']}), \
                patch.object(host_bridge, 'run', return_value={'ok': True, 'address': '10.1.1.7:3306'}) as run:
            result = connections.test('alice', 'erp')
        run.assert_called_once()
        self.assertEqual((run.call_args.args[:2], run.call_args.kwargs['agent']), (('tcp-check', {'target': 'db01:3306'}), 'ag_0123456789ab'))
        self.assertTrue(result['ok'])
        self.assertIn('10.1.1.7:3306', result['detail'])
        with patch.object(agent_hub, 'online', return_value=True), patch.object(agent_hub, 'state', return_value={'actions': ['tcp-check']}), \
                patch.object(host_bridge, 'run', side_effect=ValueError('db01: name not resolved on this PC')):
            failed = connections.test('alice', 'erp')
        self.assertEqual((failed['ok'], failed['detail']), (False, 'db01: name not resolved on this PC'))


if __name__ == '__main__':
    unittest.main()
