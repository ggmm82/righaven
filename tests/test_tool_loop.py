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


class ToolLoopTests(unittest.TestCase):
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

    def test_worker_executes_tools_and_retries_a_premature_final_response(self):
        from righaven import tool_loop
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
        from unittest.mock import Mock
        request = Mock(side_effect=responses)
        with patch.object(tool_loop, 'Path', side_effect=path), \
             patch.object(tool_loop.subprocess, 'run', wraps=subprocess.run) as execute:
            self.assertEqual(tool_loop.run('model-x', 'Make report', output, 900, progress=progress, transport=request), 'Completed')
        self.assertEqual(execute.call_args.kwargs['timeout'], 600)
        self.assertIn(('planning', 'Creo il report e controllo il contenuto'), events)
        self.assertTrue(any(event[0] == 'running_tool' for event in events))
        self.assertEqual((output / 'report.txt').read_text().strip(), 'verified')
        self.assertEqual(request.call_count, 3)
        self.assertTrue(any('La consegna non è ancora valida' in (m.get('content') or '')
            for m in request.call_args.args[1]['messages']))
        self.assertEqual(request.call_args.args[1]['messages'][-2]['role'], 'tool')

    def test_reserved_final_turn_submits_existing_files_instead_of_failing(self):
        from righaven import tool_loop
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
        def respond(route, payload, timeout):
            calls.append(payload.copy())
            if len(calls) < tool_loop.MAX_TURNS:
                command = 'echo Verified > report.txt' if len(calls) == tool_loop.MAX_TURNS - 2 else 'true'
                if len(calls) == tool_loop.MAX_TURNS - 2:
                    self.assertNotIn('tool_choice', payload)
                    self.assertEqual(payload['tools'][0]['function']['name'], 'run_command')
                tool = {'name': 'run_command', 'arguments': json.dumps({'command': command})}
            else:
                self.assertEqual(payload['tools'], [tool_loop.HANDOFF_TOOL])
                self.assertEqual(payload['tool_choice']['function']['name'], 'submit_handoff')
                tool = {'name': 'submit_handoff', 'arguments': json.dumps(manifest)}
            return {'choices': [{'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': str(len(calls)), 'type': 'function', 'function': tool}]}}]}
        with patch.object(tool_loop, 'Path', side_effect=path):
            result = tool_loop.run('model-x', 'Create report', output, 30, transport=respond)
        self.assertIn('report.txt', result)
        self.assertEqual(len(calls), tool_loop.MAX_TURNS)
        self.assertEqual(json.loads((output / 'handoff.json').read_text()), manifest)
        self.assertEqual((output / 'handoff.json').stat().st_mode & 0o777, 0o600)

    def test_finalization_tool_rejects_missing_files_without_false_manifest(self):
        from righaven.tool_loop import submit_handoff
        output = Path(self.temp.name) / 'output'
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'mancante'):
            submit_handoff(output, {'task': 'Report', 'source_files': [],
                'output_files': [str(output / 'missing.pdf')], 'previews': [],
                'checks': [{'name': 'Export', 'status': 'not_run', 'evidence': 'Not generated'}], 'warnings': []})
        self.assertFalse((output / 'handoff.json').exists())
        self.assertFalse(list(output.glob('.handoff-*')))

    def test_internal_catalog_cannot_be_reported_as_a_product(self):
        from righaven.tool_loop import submit_handoff
        output = Path(self.temp.name) / 'output'
        (output / 'work').mkdir(parents=True)
        catalog = output / 'work/catalog.json'
        catalog.write_text('{"tools": []}')
        with self.assertRaisesRegex(ValueError, 'file tecnici'):
            submit_handoff(output, {'task': 'Create robot', 'source_files': [],
                'output_files': [str(catalog)], 'previews': [],
                'checks': [{'name': 'Product', 'status': 'not_run', 'evidence': 'Only discovery completed'}], 'warnings': []})
        self.assertFalse((output / 'handoff.json').exists())

    def test_truncated_reply_asks_for_smaller_steps_instead_of_failing(self):
        root = Path(self.temp.name)
        output = root / 'output'
        (output / 'work').mkdir(parents=True)
        credentials = root / 'api.json'
        credentials.write_text(json.dumps({'api_key': 'test-only-key'}))
        seen = []
        def respond(route, payload, timeout):
            seen.append([m.get('content') for m in payload['messages']])
            if len(seen) == 1:
                return {'choices': [{'finish_reason': 'length', 'message': {'role': 'assistant', 'content': None,
                    'tool_calls': [{'id': 'cut', 'type': 'function', 'function': {'name': 'run_command', 'arguments': '{"command": "cat > big'}}]}}]}
            return {'choices': [{'message': {'role': 'assistant', 'content': 'stop'}}]}
        from righaven import tool_loop
        with patch.object(tool_loop, 'Path', side_effect=lambda v: credentials if v == '/credentials/api.json' else Path(v)), \
             patch.object(tool_loop, 'MAX_TURNS', 3):
            with self.assertRaises(RuntimeError):
                tool_loop.run('model-x', 'Report', output, 60, transport=respond)
        self.assertTrue(any('limite di token' in str(c) for c in seen[1]))
        # The cut tool call was never executed nor sent back.
        self.assertFalse(any(c is None for c in seen[1][2:3]))

    def test_old_command_outputs_are_shortened_when_history_grows(self):
        from righaven import tool_loop
        messages = [{'role': 'system', 'content': 'p'}, {'role': 'user', 'content': 'u'}]
        for i in range(30):
            messages.append({'role': 'assistant', 'content': None, 'tool_calls': [{'id': str(i)}]})
            messages.append({'role': 'tool', 'tool_call_id': str(i), 'content': 'x' * 8000})
        self.assertTrue(tool_loop.compact(messages))
        self.assertLess(len(messages[3]['content']), 1300)
        self.assertEqual(len(messages[-1]['content']), 8000)  # recent outputs stay complete
        self.assertEqual(len(messages), 62)


class DeepSeekMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_shared_deepseek_profile_becomes_an_openai_compatible_connection(self):
        import yaml
        from righaven import provider_migration
        (self.base / 'credentials/.deepseek').mkdir(parents=True)
        (self.base / 'credentials/.deepseek/api.json').write_text(json.dumps({'api_key': 'sk-test'}))
        (self.base / 'config.yaml').write_text(yaml.safe_dump({'models': [
            {'name': 'rh-codex', 'use': provider_migration.OLD_PROVIDER, 'model': 'deepseek-chat'},
            {'name': 'rh-squad', 'use': 'righaven.codex_provider:HarnessCodexChatModel', 'model': 'gpt'}]}))
        (self.base / 'agents.json').write_text(json.dumps({'gridcraft': {'engine': 'deepseek', 'model': 'deepseek-chat'}}))
        self.assertTrue(provider_migration.migrate(self.base, None))
        models = yaml.safe_load((self.base / 'config.yaml').read_text())['models']
        self.assertEqual(models[0]['use'], provider_migration.NEW_PROVIDER)
        self.assertEqual(models[0]['model'], 'deepseek-chat')
        connection = json.loads((self.base / 'credentials/.openai' / (models[0]['connection_id'] + '.json')).read_text())
        self.assertEqual((connection['api_key'], connection['base_url']), ('sk-test', 'https://api.deepseek.com'))
        self.assertEqual(models[1]['use'], 'righaven.codex_provider:HarnessCodexChatModel')
        self.assertEqual(json.loads((self.base / 'agents.json').read_text())['gridcraft']['engine'], 'inherit')
        self.assertFalse((self.base / 'credentials/.deepseek/api.json').exists())
        self.assertFalse(provider_migration.migrate(self.base, None))  # once

    def test_hosted_organization_profile_is_migrated_encrypted(self):
        from cryptography.fernet import Fernet, MultiFernet
        from righaven import provider_migration
        cipher = MultiFernet([Fernet(Fernet.generate_key())])
        organization = self.base / 'organizations/org1'
        (organization / 'credentials/.deepseek').mkdir(parents=True)
        secret = {'api_key': 'sk-hosted', 'base_url': None, 'connection_id': None}
        (organization / 'credentials/.deepseek/api.json').write_text(json.dumps(
            {'format': 'fernet:v2', 'encrypted': cipher.encrypt(json.dumps(secret).encode()).decode()}))
        (organization / 'models.json').write_text(json.dumps({'coordinator': {'engine': 'deepseek', 'model': 'deepseek-chat', 'connection_id': None}}))
        self.assertTrue(provider_migration.migrate(self.base, cipher))
        profile = json.loads((organization / 'models.json').read_text())['coordinator']
        self.assertEqual(profile['engine'], 'openai')
        stored = json.loads((organization / 'credentials/.openai' / (profile['connection_id'] + '.json')).read_text())
        value = json.loads(cipher.decrypt(stored['encrypted'].encode()))
        self.assertEqual((value['api_key'], value['base_url']), ('sk-hosted', 'https://api.deepseek.com'))
        self.assertNotIn('sk-hosted', (organization / 'credentials/.openai' / (profile['connection_id'] + '.json')).read_text())

    def test_compatible_model_with_vision_can_attest_visual_checks(self):
        from righaven.acceptance import capabilities
        self.assertTrue(capabilities('openai', vision=True)['visual'])
        self.assertFalse(capabilities('openai', vision=False)['visual'])
        self.assertTrue(capabilities('claude')['visual'])
        self.assertFalse(capabilities('openai', vision=True)['listening'])

    def test_deepseek_endpoint_keeps_thinking_off_for_tool_calls(self):
        from righaven.openai_compatible import provider_options
        self.assertEqual(provider_options('https://api.deepseek.com'), {'thinking': {'type': 'disabled'}})
        self.assertEqual(provider_options('https://api.deepseek.com', reasoning=True), {})
        self.assertEqual(provider_options('https://api.openai.com/v1'), {})


if __name__ == '__main__':
    unittest.main()
