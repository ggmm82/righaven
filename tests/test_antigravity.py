"""Regressions for official CLI transport and coordinator isolation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from righaven import antigravity_cli as cli, antigravity_protocol as protocol
from righaven.run_agent import command, copy_credentials

TOOLS = [{'type': 'function', 'function': {'name': 'harness_delegate',
    'parameters': {'type': 'object', 'properties': {'agent': {'type': 'string'}}}}}]


class AntigravityTests(unittest.TestCase):
    def test_delegation_history_and_tool_schema_survive_cli_boundary(self):
        first = protocol.response({'content': '', 'tool_calls': [
            {'name': 'harness_delegate', 'args': {'agent': 'cadcraft'}}]}, TOOLS)
        messages = [{'type': 'system', 'content': 'Italiano'},
            {'type': 'human', 'content': 'Crea un modello modificabile'},
            {'type': 'ai', **first},
            {'type': 'tool', 'tool_call_id': first['tool_calls'][0]['id'], 'content': 'verified.dxf'}]
        payload = protocol.request(messages, 'chosen-model', TOOLS)
        self.assertIn('verified.dxf', payload['prompt'])
        self.assertIn(first['tool_calls'][0]['id'], payload['prompt'])
        self.assertEqual(payload['schema']['properties']['tool_calls']['items']['anyOf'][0]
                         ['properties']['name']['enum'], ['harness_delegate'])
        self.assertEqual(protocol.response({'content': 'Ecco il DXF.', 'tool_calls': []})['content'], 'Ecco il DXF.')

    def test_rejects_empty_unauthorized_and_unmatched_decisions(self):
        for decision in ({'content': '', 'tool_calls': []}, {'content': '', 'tool_calls': [
                {'name': 'run_command', 'args': {'command': 'touch fake.dxf'}}]}):
            with self.assertRaises(RuntimeError):
                protocol.response(decision, TOOLS)
        with self.assertRaises(ValueError):
            protocol.request([{'type': 'tool', 'content': 'fake', 'tool_call_id': 'missing'}], 'auto')
        with self.assertRaises(ValueError):
            protocol.request([{'type': 'human', 'content': [{'type': 'image_url', 'image_url': 'https://example.test'}]}], 'auto')
        forced = protocol.request([], 'auto', TOOLS, 'required')
        self.assertEqual(forced['schema']['properties']['tool_calls']['minItems'], 1)
        self.assertEqual(protocol.request([], 'auto', TOOLS, 'none')['schema']['properties']['tool_calls']['maxItems'], 0)

    def test_native_stream_schema_and_permissions_isolate_the_coordinator(self):
        envelope = {'status': 'SUCCESS', 'structured_output': {'content': 'Pronto', 'tool_calls': []},
                    'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}}
        with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)), \
             patch.object(cli.subprocess, 'run', return_value=SimpleNamespace(returncode=0,
                 stdout=json.dumps({'event': 'result', 'result': envelope}))) as run:
            value = cli.generate(protocol.request([{'type': 'human', 'content': 'Brief'}], 'chosen-model'))
            args, options = run.call_args.args[0], run.call_args.kwargs
            self.assertNotIn('--dangerously-skip-permissions', args)
            self.assertEqual(args[args.index('--model')+1], 'chosen-model')
            self.assertEqual(json.loads(options['input'])['message']['content'].count('Brief'), 1)
            settings = json.loads((Path(directory)/'.gemini/antigravity-cli/settings.json').read_text())
            self.assertIn('command(*)', settings['permissions']['deny'])
            self.assertIn('write_file(*)', settings['permissions']['deny'])
            self.assertFalse(settings['useG1Credits'])
            agent = (Path(directory)/'.gemini/config/agents/skill-coordinator.md').read_text()
            self.assertIn('tools: [finish]', agent)
            self.assertEqual(value['content'], 'Pronto')
        for status in ('ERROR', 'WAITING', 'CANCELED', 'INTERRUPTED'):
            with tempfile.TemporaryDirectory() as directory, patch.object(Path, 'home', return_value=Path(directory)), \
                 patch.object(cli.subprocess, 'run', return_value=SimpleNamespace(returncode=0,
                     stdout=json.dumps({'event': 'result', 'result': {'status': status}}))):
                with self.assertRaises(RuntimeError):
                    cli.generate(protocol.request([], 'auto'))

    def test_worker_uses_same_model_and_official_cli_and_only_copies_native_tokens(self):
        args = command('gemini', 'chosen-model', 'private brief', '/tmp/final')
        self.assertEqual(args[0], 'agy')
        self.assertNotIn('private brief', args)
        self.assertIn('--dangerously-skip-permissions', args)
        self.assertNotIn('--model', command('gemini', 'auto', 'Task', '/tmp/final'))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';target=root/'target'
            (source/'antigravity-cli').mkdir(parents=True)
            (source/cli.TOKEN).write_text('fixture-token')
            (source/'oauth_creds.json').write_text('old-gemini')
            (source/'antigravity-cli/conversation.json').write_text('private-history')
            copy_credentials(source,target,'gemini')
            self.assertEqual((target/cli.TOKEN).read_text(),'fixture-token')
            self.assertEqual((target/cli.TOKEN).stat().st_mode & 0o777,0o600)
            self.assertFalse((target/'oauth_creds.json').exists())
            self.assertFalse((target/'antigravity-cli/conversation.json').exists())
            (target/cli.TOKEN).unlink();(target/cli.TOKEN).symlink_to(source/cli.TOKEN)
            with self.assertRaises(ValueError):cli.copy_auth(source,target)

    def test_live_catalog_parser_uses_native_slugs_and_rejects_auth_failure(self):
        result=SimpleNamespace(returncode=0,stdout='Fetching available models...\ngemini-4-argon-high\tGemini 4 Argon (High)\ngemini-3.8-flash-medium   Gemini 3.8 Flash (Medium)\n')
        with patch.object(cli.subprocess,'run',return_value=result):
            self.assertEqual([x['id'] for x in cli.models()],['gemini-4-argon-high','gemini-3.8-flash-medium'])
        with patch.object(cli.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='private-token')):
            with self.assertRaisesRegex(RuntimeError,'login Google'):cli.models()

    def test_external_api_keys_cannot_override_subscription_authentication(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fixture','GOOGLE_GEMINI_BASE_URL':'https://example.test','HTTPS_PROXY':'http://proxy:8080'}):
            env=cli.cli_env()
            self.assertNotIn('GEMINI_API_KEY',env)
            self.assertNotIn('GOOGLE_GEMINI_BASE_URL',env)
            self.assertEqual(env['HTTPS_PROXY'],'http://proxy:8080')
        for output in ('{}','{"event":"result","result":{}}\n{"event":"result","result":{}}'):
            with self.assertRaises(ValueError):cli.result_envelope(output)


if __name__=='__main__':unittest.main()

class TerminalLoginTests(unittest.TestCase):
    def test_stream_split_hyperlinks_and_utf8_do_not_create_duplicate_oauth_links(self):
        from righaven.terminal_text import TerminalText, authorization_url
        url='https://accounts.google.com/o/oauth2/auth?client_id=fixture&code_challenge=pkce&redirect_uri=https%3A%2F%2Fantigravity.google%2Foauth-callback&scope=openid&state=new&response_type=code'
        wire=('Apri '+url+'\n\x1b]8;;'+url+'\x07→ Click here\x1b]8;;\x07\nCaffè\x1b[31m!\x1b[0m').encode()
        decoder=TerminalText();text=''.join(decoder.feed(bytes([b])) for b in wire)
        self.assertEqual(text,'Apri '+url+'\n→ Click here\nCaffè!')
        self.assertEqual(authorization_url(text,'gemini'),url)
        self.assertEqual(text.count(url),1)
        newer=url.replace('state=new','state=newer')
        self.assertEqual(authorization_url(text+'\n'+newer+'\x07→','gemini'),newer)
        self.assertIsNone(authorization_url('https://accounts.google.com/o/oauth2/auth?client_id=partial','gemini'))
        self.assertEqual(authorization_url('https://auth.openai.com/codex/device','codex'),'https://auth.openai.com/codex/device')

    def test_login_public_state_reports_failure_and_resumes_same_session(self):
        import threading
        from righaven import login
        session=login.LoginSession.__new__(login.LoginSession)
        session.id='fixture-session';session.engine='gemini';session.text='{"ok":false,"error":"Codice Google non valido o scaduto"}\n'
        session._lock=threading.Lock();session.closed=True;session.returncode=1;session.input_sent=True
        value=session.public()
        self.assertIn('non valido',value['error'])
        self.assertTrue(value['input_sent'])
        session.closed=False
        with patch.dict(login.SESSIONS,{'fixture-session':session},clear=True),patch.object(login,'LoginSession') as create:
            self.assertEqual(login.start('gemini')['id'],'fixture-session')
            create.assert_not_called()
