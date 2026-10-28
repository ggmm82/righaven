import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def report_delivery(path):
    return {'source_status': 'not_applicable', 'source_note': 'Analysis report only', 'files': [{
        'path': str(path), 'role': 'report', 'format': 'TXT', 'open_with': 'Text editor',
        'editability': 'Report text', 'reopen': {'status': 'passed', 'evidence': 'Read report.txt'},
        'limitations': []}]}


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'RIGHAVEN_STATE': self.temp.name,
            'RIGHAVEN_PASSWORD': 'test-password-at-least-16-characters'})
        self.environment.start()
        from righaven import state, bootstrap, router
        self.state = importlib.reload(state)
        self.bootstrap = importlib.reload(bootstrap)
        self.bootstrap.initialize()
        self.router = importlib.reload(router)
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(self.router.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.environment.stop()
        self.temp.cleanup()

    def test_browser_connection_configures_real_provider_without_exposing_key(self):
        key = 'test-only-secret-value'
        with patch('righaven.deepseek.models', return_value=['deepseek-flash']):
            response = self.client.put('/harness/api/providers/deepseek', json={'api_key': key},
                headers={'origin': 'http://testserver'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['model'], 'deepseek-flash')
        config = (self.state.STATE / 'config.yaml').read_text()
        self.assertIn('righaven.deepseek_provider:HarnessDeepSeekChatModel', config)
        public = self.client.get('/harness/api/catalog').text + response.text + config
        self.assertNotIn(key, public)
        self.assertTrue(self.state.connection_status('deepseek'))
        self.state.update_agent('gridcraft', {'engine': 'deepseek'})
        self.assertEqual(self.state.catalog()['gridcraft']['engine'], 'deepseek')
        self.assertEqual((self.state.credential_dir('deepseek') / 'api.json').stat().st_mode & 0o777, 0o600)

    def test_rejected_key_and_cross_origin_do_not_change_credentials(self):
        with patch('righaven.deepseek.models', side_effect=ValueError('Chiave DeepSeek rifiutata')) as models:
            response = self.client.put('/harness/api/providers/deepseek', json={'api_key': 'bad-key'},
                headers={'origin': 'https://other.example'})
            self.assertEqual(response.status_code, 403)
            models.assert_not_called()
            response = self.client.put('/harness/api/providers/deepseek', json={'api_key': 'bad-key'},
                headers={'origin': 'http://testserver'})
            self.assertEqual(response.status_code, 400)
        self.assertFalse(self.state.connection_status('deepseek'))

    def test_worker_executes_tools_and_retries_a_premature_final_response(self):
        from righaven import deepseek
        root = Path(self.temp.name)
        output = root / 'output'
        (output / 'work').mkdir(parents=True)
        credentials = root / 'api.json'
        credentials.write_text(json.dumps({'api_key': 'test-only-key'}))
        def path(value):
            return credentials if value == '/credentials/api.json' else Path(value)
        import shlex
        manifest = {'task': 'Report', 'source_files': [], 'output_files': [str(output / 'report.txt')],
                    'checks': [{'name': 'Content', 'status': 'passed', 'evidence': 'Read report.txt'}], 'warnings': []}
        manifest['delivery'] = report_delivery(output / 'report.txt')
        command = 'echo verified > report.txt; printf %s ' + shlex.quote(json.dumps(manifest)) + ' > handoff.json'
        responses = [
            {'choices': [{'message': {'role': 'assistant', 'content': 'Premature completion'}}]},
            {'choices': [{'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': '0', 'type': 'function', 'function': {
                    'name': 'report_progress', 'arguments': json.dumps({'phase': 'planning', 'summary': 'Creo il report e controllo il contenuto'})}},
                    {'id': '1', 'type': 'function', 'function': {
                    'name': 'run_command', 'arguments': json.dumps({'command': command, 'timeout_seconds': 600})}}]}}]},
            {'choices': [{'message': {'role': 'assistant', 'content': 'Completed'}}]},
        ]
        events = []
        from types import SimpleNamespace
        progress = SimpleNamespace(model_signal=lambda: None, emit=lambda *args, **kwargs: events.append(args))
        import subprocess
        with patch.object(deepseek, 'Path', side_effect=path), \
             patch.object(deepseek, 'request', side_effect=responses) as request, \
             patch.object(deepseek.subprocess, 'run', wraps=subprocess.run) as execute:
            self.assertEqual(deepseek.run('deepseek-flash', 'Make report', output, 900, progress=progress), 'Completed')
        self.assertEqual(execute.call_args.kwargs['timeout'], 600)
        self.assertIn(('planning', 'Creo il report e controllo il contenuto'), events)
        self.assertTrue(any(event[0] == 'running_tool' for event in events))
        self.assertEqual((output / 'report.txt').read_text().strip(), 'verified')
        self.assertEqual(request.call_count, 3)
        self.assertTrue(any('La consegna non è ancora valida' in (m.get('content') or '')
            for m in request.call_args.args[2]['messages']))
        self.assertEqual(request.call_args.args[2]['messages'][-2]['role'], 'tool')

    def test_reserved_final_turn_submits_existing_files_instead_of_failing(self):
        from righaven import deepseek
        root = Path(self.temp.name)
        output = root / 'output'
        (output / 'work').mkdir(parents=True)
        credentials = root / 'api.json'
        credentials.write_text(json.dumps({'api_key': 'test-only-key'}))
        manifest = {'task': 'Report', 'source_files': [], 'output_files': [str(output / 'report.txt')],
                    'previews': [], 'checks': [{'name': 'Content', 'status': 'passed',
                    'evidence': 'Read report.txt'}], 'warnings': []}
        def path(value):
            return credentials if value == '/credentials/api.json' else Path(value)
        manifest['delivery'] = report_delivery(output / 'report.txt')
        calls = []
        def respond(key, route, payload, timeout):
            calls.append(payload.copy())
            if len(calls) < deepseek.MAX_TURNS:
                command = 'echo Verified > report.txt' if len(calls) == deepseek.MAX_TURNS - 2 else 'true'
                if len(calls) == deepseek.MAX_TURNS - 2:
                    self.assertNotIn('tool_choice', payload)
                    self.assertEqual(payload['tools'][0]['function']['name'], 'run_command')
                tool = {'name': 'run_command', 'arguments': json.dumps({'command': command})}
            else:
                self.assertEqual(payload['tools'], [deepseek.HANDOFF_TOOL])
                self.assertEqual(payload['tool_choice']['function']['name'], 'submit_handoff')
                tool = {'name': 'submit_handoff', 'arguments': json.dumps(manifest)}
            return {'choices': [{'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': str(len(calls)), 'type': 'function', 'function': tool}]}}]}
        with patch.object(deepseek, 'Path', side_effect=path), patch.object(deepseek, 'request', side_effect=respond):
            result = deepseek.run('deepseek-flash', 'Create report', output, 30)
        self.assertIn('report.txt', result)
        self.assertEqual(len(calls), deepseek.MAX_TURNS)
        self.assertEqual(json.loads((output / 'handoff.json').read_text()), manifest)
        self.assertEqual((output / 'handoff.json').stat().st_mode & 0o777, 0o600)

    def test_finalization_tool_rejects_missing_files_without_false_manifest(self):
        from righaven.deepseek import submit_handoff
        output = Path(self.temp.name) / 'output'
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'mancante'):
            submit_handoff(output, {'task': 'Report', 'source_files': [],
                'output_files': [str(output / 'missing.pdf')], 'previews': [],
                'checks': [{'name': 'Export', 'status': 'not_run', 'evidence': 'Not generated'}], 'warnings': []})
        self.assertFalse((output / 'handoff.json').exists())
        self.assertFalse(list(output.glob('.handoff-*')))

    def test_internal_catalog_cannot_be_reported_as_a_product(self):
        from righaven.deepseek import submit_handoff
        output = Path(self.temp.name) / 'output'
        (output / 'work').mkdir(parents=True)
        catalog = output / 'work/catalog.json'
        catalog.write_text('{"tools": []}')
        with self.assertRaisesRegex(ValueError, 'file tecnici'):
            submit_handoff(output, {'task': 'Create robot', 'source_files': [],
                'output_files': [str(catalog)], 'previews': [],
                'checks': [{'name': 'Product', 'status': 'not_run', 'evidence': 'Only discovery completed'}], 'warnings': []})
        self.assertFalse((output / 'handoff.json').exists())

    def test_transport_does_not_reflect_provider_error_body(self):
        import io
        import urllib.error
        from righaven import deepseek
        error = urllib.error.HTTPError('https://api.deepseek.com/models', 401, 'Unauthorized', {},
            io.BytesIO(b'provider-reflected-test-key'))
        with patch.object(deepseek.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(ValueError, '^Chiave DeepSeek rifiutata$'):
                deepseek.models('test-key')


if __name__ == '__main__':
    unittest.main()
