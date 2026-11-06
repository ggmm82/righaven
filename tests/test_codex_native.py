"""Real pinned Codex against a loopback-only fixture, plus asset boundaries."""
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from righaven.codex_native import export_image, png_info, run

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==')


class NativeAssetTests(unittest.TestCase):
    def test_exact_bytes_and_provenance_but_no_claim_of_vector_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); home = root / 'auth'; source = home / 'generated_images/session/call.png'
            source.parent.mkdir(parents=True); source.write_bytes(PNG)
            out = root / 'output'; out.mkdir()
            item = {'id':'fixture','status':'completed','savedPath':str(source),'revisedPrompt':'Blue whale'}
            record = export_image(item, out, home)
            self.assertEqual(Path(record['path']).read_bytes(), PNG)
            self.assertEqual((record['width'], record['height']), (1, 1))
            self.assertIn('raster', ' '.join(record['limits']))
            self.assertEqual(export_image(item, out, home), record)
            for path in (home / 'auth.json', home / 'generated_images/../auth.json'):
                with self.assertRaises(ValueError):
                    export_image({**item, 'savedPath':str(path)}, out, home)
            source.unlink(); source.symlink_to(root / 'secret')
            with self.assertRaises(ValueError):
                export_image(item, out, home)

    def test_invalid_or_incomplete_images_are_rejected(self):
        for data in (b'not png', PNG[:-4], PNG[:40] + b'BAD!' + PNG[44:], PNG + b'junk'):
            with self.assertRaises(ValueError): png_info(data)
        from righaven.work_results import failure_info
        for failure, code in ((None, 'work_error'), ({'type': 'usageLimitExceeded'}, 'provider_quota')):
            with self.assertRaises(RuntimeError) as error:
                export_image({'status': 'failed', 'failure': failure}, Path('/unused'), Path('/unused'))
            self.assertEqual(failure_info(error.exception)['code'], code)

    def test_unresponsive_startup_has_a_separate_limit_and_reaps_the_process(self):
        from righaven.cli_runner import ProviderSilence
        from righaven.work_results import failure_info
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'hung-codex'
            pid = root / 'pid'
            binary.write_text('#!' + sys.executable + '\nimport os,time,pathlib\npathlib.Path(' + repr(str(pid)) + ').write_text(str(os.getpid()))\ntime.sleep(20)\n')
            binary.chmod(0o700)
            progress = Mock(); progress.model_wait_seconds = 0
            with patch('righaven.codex_native.STARTUP_TIMEOUT', .25):
                with self.assertRaises(ProviderSilence) as error:
                    run('fixture','Private prompt',root,5,progress,executable=str(binary))
            self.assertEqual(failure_info(error.exception)['code'],'provider_startup_limit')
            with self.assertRaises(ProcessLookupError): os.kill(int(pid.read_text()),0)
            self.assertFalse(any(c.args[0]=='waiting_model' for c in progress.emit.call_args_list))


BINARY = os.getenv('CODEX_TEST_BINARY') or shutil.which('codex')
REQUIRE = os.getenv('RIGHAVEN_REQUIRE_CODEX_NATIVE_TESTS') == '1'


@unittest.skipUnless(BINARY or REQUIRE, 'Pinned Codex CLI required for native protocol check')
class NativeProtocolTests(unittest.TestCase):
    def test_real_cli_image_events_transfer_and_vector_feature_disable(self):
        self.assertTrue(BINARY, 'Pinned Codex executable missing')
        version = subprocess.check_output([BINARY, '--version'], text=True).strip()
        lock = Path(__file__).resolve().parents[1] / 'versions.lock.json'
        if not lock.is_file(): lock = Path('/opt/righaven/versions.lock.json')
        pinned = json.loads(lock.read_text())['cli_runtimes']['codex']
        if version != 'codex-cli ' + pinned:
            if REQUIRE or os.getenv('CODEX_TEST_BINARY'):
                self.fail('Contract requires codex-cli ' + pinned + ': ' + version)
            self.skipTest('Contract targets pinned ' + pinned + ', installed ' + version)
        requests = []
        image_enabled = [True]
        command_enabled = [False]
        response_count = [0]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def reply(self, value):
                self.send_response(200); self.send_header('Content-Type','application/json'); self.end_headers()
                self.wfile.write(json.dumps(value).encode())
            def do_GET(self):
                if self.path.endswith('/models') or '/models?' in self.path:
                    return self.reply({'models':[]})
                if self.path.endswith('/accounts/check'):
                    return self.reply({'accounts':[{'id':'fixture-account','workspace_backend_origin':'https://chatgpt.com','account_routing_override':'NO_CONSTRAINT'}]})
                self.reply({})
            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get('Content-Length',0)))
                try: body = json.loads(raw or '{}')
                except (ValueError, UnicodeDecodeError): return self.reply({})
                requests.append((self.path,body))
                if self.path.endswith('/images/generations'):
                    return self.reply({'created':1,'background':'opaque','data':[{'b64_json':base64.b64encode(PNG).decode()}]})
                if self.path.endswith('/responses'):
                    response_count[0] += 1
                    image_call = image_enabled[0] and response_count[0] == 1
                    item = ({'type':'function_call','namespace':'image_gen','name':'imagegen','call_id':'fixture-image','arguments':json.dumps({'prompt':'paint a blue whale'})} if image_call else
                            {'type':'message','id':'msg-fixture','role':'assistant','content':[{'type':'output_text','text':'Done'}]})
                    if command_enabled[0] and response_count[0] == 1:
                        item = {'type':'function_call','namespace':'functions','name':'exec_command','call_id':'fixture-command','arguments':json.dumps({'cmd':'printf native-cli-ok > command-result.txt','yield_time_ms':1000})}
                    frames = [{'type':'response.created','response':{'id':'resp-fixture'}},
                              {'type':'response.output_item.added','output_index':0,'item':item},
                              {'type':'response.output_item.done','output_index':0,'item':item},
                              {'type':'response.completed','response':{'id':'resp-fixture','status':'completed','output':[item], 'usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}}]
                    self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
                    self.wfile.write(''.join('data: '+json.dumps(f)+'\n\n' for f in frames).encode()); return
                self.reply({})
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); home = root / 'codex'; home.mkdir(); out = root / 'output'; out.mkdir()
            uri = 'http://127.0.0.1:' + str(server.server_port)
            (home / 'config.toml').write_text(f'''model = "gpt-5.4"
model_provider = "openai-custom"
chatgpt_base_url = "{uri}"
[model_providers.openai-custom]
name = "OpenAI"
base_url = "{uri}/api/codex"
wire_api = "responses"
requires_openai_auth = true
supports_websockets = false
[features]
enable_request_compression = false
''')
            jwt = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
            fake_id = jwt({'alg':'none'})+'.'+jwt({'email':'fixture@example.invalid','https://api.openai.com/auth':{'chatgpt_account_id':'fixture-account','chatgpt_plan_type':'plus'}})+'.fixture'
            (home / 'auth.json').write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'id_token':fake_id,'access_token':'fixture-not-a-real-token','refresh_token':'fixture-not-a-real-refresh','account_id':'fixture-account'},'last_refresh':datetime.now(timezone.utc).isoformat()}))
            env = {**os.environ,'CODEX_HOME':str(home),'HOME':str(root)}
            # Never use a real inherited account or key, even in developer shells.
            for key in ('OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CODEX_INTERNAL_ORIGINATOR_OVERRIDE'):
                env.pop(key,None)
            progress = Mock(); progress.model_wait_seconds = 0
            self.assertEqual(run('gpt-5.4','Generate one blue whale.',out,40,progress,env=env,executable=BINARY), 'Done')
            events = [c.args[1] for c in progress.cli_event.call_args_list]
            self.assertTrue(any(e.get('type')=='item.started' and e.get('item',{}).get('type')=='image_generation' for e in events))
            self.assertTrue(any(e.get('type')=='item.completed' and e.get('item',{}).get('type')=='image_generation' for e in events))
            self.assertEqual(next((out/'generated_images').glob('*.png')).read_bytes(), PNG)
            self.assertEqual(len(list((out/'work').glob('imagegen-*.json'))),1)
            count = len([p for p,b in requests if p.endswith('/images/generations')])
            self.assertEqual(count,1)
            image_enabled[0] = False; response_count[0] = 0
            self.assertEqual(run('gpt-5.4','Create editable vectors only.',out,40,progress,env=env,executable=BINARY,image_generation=False),'Done')
            last = [b for p,b in requests if p.endswith('/responses')][-1]
            self.assertNotIn('image_gen', json.dumps(last.get('tools')))
            command_enabled[0] = True; response_count[0] = 0
            self.assertEqual(run('gpt-5.4','Run the command.',out,40,progress,env=env,executable=BINARY,image_generation=False),'Done')
            self.assertEqual((out/'command-result.txt').read_text(),'native-cli-ok')
            self.assertTrue(any(c.args[1].get('item',{}).get('type')=='command_execution' for c in progress.cli_event.call_args_list))
            command_enabled[0] = False; response_count[0] = 0
            original=(out/'command-result.txt').read_bytes()
            checked=Mock(side_effect=[ValueError('delivery.components[0].tool: massimo 48 caratteri'),None])
            self.assertEqual(run('gpt-5.4','Finalize existing files.',out,40,progress,env=env,executable=BINARY,
                                 image_generation=False,preflight=checked),'Done')
            self.assertEqual(checked.call_count,2)
            self.assertEqual(response_count[0],2)
            self.assertEqual((out/'command-result.txt').read_bytes(),original)
            checked=Mock(side_effect=ValueError('Still invalid'))
            response_count[0]=0
            with self.assertRaisesRegex(ValueError,'Still invalid'):
                run('gpt-5.4','Finalize existing files.',out,40,progress,env=env,executable=BINARY,
                    image_generation=False,preflight=checked)
            self.assertEqual(checked.call_count,2)
            self.assertEqual(response_count[0],2)
