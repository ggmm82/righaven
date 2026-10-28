"""Real local HTTP contracts, scope isolation and private worker credentials."""
import importlib
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

try:
    from righaven.openai_provider import HarnessCompatibleChatModel
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    HarnessCompatibleChatModel = None


class CustomProviderTests(unittest.TestCase):
    def setUp(self):
        from righaven.resource_budget import ResourceBudget
        budget_patch = patch('righaven.resource_budget.BUDGET', ResourceBudget())
        budget_patch.start(); self.addCleanup(budget_patch.stop)
        publisher = patch('righaven.task_staging.TaskStaging.publish', side_effect=lambda result: result)
        publisher.start(); self.addCleanup(publisher.stop)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'RIGHAVEN_STATE': self.temp.name, 'RIGHAVEN_PASSWORD': 'fixture-private-password-123456',
            'RIGHAVEN_CONFIG_PATH': str(self.root/'config.yaml'),
            'RIGHAVEN_EXTENSIONS_CONFIG_PATH': str(self.root/'extensions_config.json')})
        self.env.start(); self.addCleanup(self.env.stop)
        from righaven import state, bootstrap, router, docker_runtime
        self.state = importlib.reload(state); self.bootstrap = importlib.reload(bootstrap)
        self.bootstrap.initialize(); self.runtime = importlib.reload(docker_runtime)
        self.router = importlib.reload(router)
        (self.state.credential_dir('codex') / 'auth.json').write_text('{}')
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI();app.include_router(self.router.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)
        self.requests = []; owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def respond(self, data, code=200):
                self.send_response(code);self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            def do_GET(self):
                owner.requests.append(('GET',self.path,None,self.headers.get('Authorization')))
                if 'missing-models' in self.path: return self.respond({},404)
                self.respond({'data':[{'id':'Acme/Model-X'},{'id':'Acme/Model-Y'}]})
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append(('POST',self.path,body,self.headers.get('Authorization')))
                if 'completion-token' in self.path and 'max_tokens' in body:return self.respond({},400)
                if 'required-choice' in self.path and isinstance(body.get('tool_choice'),dict):return self.respond({},400)
                if 'auto-choice' in self.path and 'tool_choice' in body:return self.respond({},400)
                if 'no-vision' in self.path and any(isinstance(m.get('content'),list) and any(isinstance(c,dict) and c.get('type')=='image_url' for c in m['content']) for m in body.get('messages',[])):return self.respond({},400)
                if 'flaky' in self.path and owner.flaky<2:
                    owner.flaky+=1;return self.respond({'error':'transient'},500)
                if self.headers.get('Authorization') == 'Bearer rejected': return self.respond({'error':'reflected rejected'},401)
                if body.get('stream'):
                    self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                    for delta,finish in [({'role':'assistant','content':'OK'},None),({},'stop')]:
                        value={'id':'fixture','object':'chat.completion.chunk','model':body['model'],
                            'choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                        self.wfile.write(('data: '+json.dumps(value)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n');return
                message = {'role':'assistant','content':'OK'}
                if owner.tools_supported and any(t.get('function',{}).get('name')=='righaven_connection_check' for t in body.get('tools',[])):
                    message={'role':'assistant','content':None,'tool_calls':[{'id':'check','type':'function',
                        'function':{'name':'righaven_connection_check','arguments':'{}'}}]}
                if owner.worker_manifest is not None and body.get('tools'):
                    name = 'submit_handoff' if any(m.get('role')=='tool' for m in body['messages']) else 'run_command'
                    arguments = owner.worker_manifest if name=='submit_handoff' else {'command':'printf verified > report.txt'}
                    message={'role':'assistant','content':None,'tool_calls':[{'id':'call-'+name,'type':'function',
                        'function':{'name':name,'arguments':json.dumps(arguments)}}]}
                usage={'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}
                if 'reasoning' in self.path:
                    message['reasoning_content']='pensiero'
                    usage['completion_tokens_details']={'reasoning_tokens':1}
                self.respond({'id':'fixture','object':'chat.completion','model':body['model'],
                    'choices':[{'index':0,'message':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}],
                    'usage':usage})
        self.worker_manifest = None
        self.tools_supported = True
        self.flaky = 0
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:'+str(self.server.server_port)+'/v1'

    def save(self, **changes):
        value={'engine':'openai','model':'Acme/Model-X','base_url':self.base,'api_key':'fixture-private-key'}
        value.update(changes)
        return self.client.put('/harness/api/team',json=value,headers={'origin':'http://testserver'})

    def test_custom_coordinator_preserves_workers_and_other_scopes_survive_restart(self):
        original = self.state.team('squad')
        response = self.save(scope='coordinator');self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.state.team('squad'),original)
        self.assertEqual(self.state.team()['engine'],'openai')
        with patch('righaven.deepseek.models',return_value=['deepseek-chat']):
            response = self.client.put('/harness/api/team',json={'engine':'deepseek','model':'deepseek-chat','api_key':'fixture-deepseek','scope':'squad'},headers={'origin':'http://testserver'})
        self.assertEqual(response.status_code,200,response.text)
        self.bootstrap.initialize()
        self.assertEqual(self.state.team()['engine'],'openai')
        self.assertEqual(self.state.team('squad')['engine'],'deepseek')
        self.assertTrue(all(a['engine']=='deepseek' for a in self.client.get('/harness/api/catalog').json()['effective_agents'].values()))
        config=yaml.safe_load((self.root/'config.yaml').read_text())
        self.assertTrue(all(d['model']=='rh-squad' for d in config['subagents']['custom_agents'].values()))
        self.assertNotIn('fixture-private-key',json.dumps(config))
        self.assertNotIn('fixture-private-key',self.client.get('/harness/api/catalog').text)
        self.assertNotIn('thinking',self.requests[0][2])

    def test_two_custom_connections_keep_worker_credentials_when_coordinator_changes(self):
        first=self.save();self.assertEqual(first.status_code,200)
        old=self.state.team('squad'); old_path=self.state.custom_connection_path(old['connection_id'])
        second=self.save(scope='coordinator',api_key='fixture-second-key',base_url=self.base+'/other')
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(self.state.team('squad'),old)
        self.assertNotEqual(self.state.team()['connection_id'],old['connection_id'])
        captured=[]
        def execute(args,**kwargs):
            captured.append((args,json.loads(next((self.root/'jobs').glob('*.json')).read_text())))
            return SimpleNamespace(returncode=0,stdout='{"ok":true}',stderr='')
        with patch('righaven.runtime_settings.effective',return_value={'cpus':1.5,'memory_mib':1536,'tmp_mib':128}),patch.object(self.runtime,'base_arguments',return_value=[]),patch.object(self.runtime,'mount',side_effect=lambda path,target,read_only=False:str(path)+'->'+target+':'+str(read_only)),patch.object(self.runtime.subprocess,'run',side_effect=execute),patch.object(self.runtime,'remove',return_value=None):
            self.runtime.delegate('vectorcraft','Create',self.root/'workspace')
        self.assertIn(str(old_path)+'->/credentials/api.json:True',captured[0][0])
        self.assertEqual(captured[0][1]['model'],'Acme/Model-X')
        self.assertNotIn('api_key',captured[0][1])
        self.assertEqual(old_path.stat().st_mode & 0o777,0o600)

    def test_reuse_saved_key_and_manual_model_without_models_endpoint(self):
        result=self.save(base_url=self.base+'/missing-models');self.assertEqual(result.status_code,200,result.text)
        profile=result.json()['team']
        result=self.save(api_key=None,base_url=profile['base_url'],connection_id=profile['connection_id'],model='Acme/Model-Y')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['team']['connection_id'],profile['connection_id'])
        listed=self.client.get('/harness/api/team/models?engine=openai&connection_id='+profile['connection_id'])
        self.assertEqual(listed.status_code,502)
        self.assertTrue(self.state.team()['ready'])

    def test_model_discovery_before_save_never_activates_or_stores_credentials(self):
        original=(self.root/'config.yaml').read_bytes()
        response=self.client.post('/harness/api/team/models',json={'engine':'openai',
            'base_url':self.base,'api_key':'fixture-private-key'},headers={'origin':'http://testserver'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['models'],['Acme/Model-X','Acme/Model-Y'])
        self.assertEqual((self.root/'config.yaml').read_bytes(),original)
        self.assertFalse(self.state.connection_status('openai'))
        self.assertNotIn('fixture-private-key',response.text)

    def test_invalid_endpoint_key_origin_and_scope_do_not_change_profiles(self):
        self.assertEqual(self.save().status_code,200)
        original=(self.root/'config.yaml').read_bytes()
        for change in ({'api_key':'rejected'},{'base_url':'https://user:pass@example.com/v1'},
                       {'base_url':'file:///tmp/api'},{'scope':'everywhere'},
                       {'api_key':None,'base_url':self.base+'/changed'}):
            with self.subTest(change=change):self.assertIn(self.save(**change).status_code,(400,422))
            self.assertEqual((self.root/'config.yaml').read_bytes(),original)
        response=self.client.put('/harness/api/team',json={'engine':'openai','api_key':'private'},headers={'origin':'https://other.example'})
        self.assertEqual(response.status_code,403)
        self.assertEqual((self.root/'config.yaml').read_bytes(),original)

    def test_both_returns_to_shared_profile_and_native_providers_remain_available(self):
        self.assertEqual(self.save(scope='squad').status_code,200)
        with patch.object(self.runtime,'codex_models',return_value=[{'id':'gpt-6.1-sol','label':'GPT-6.1-Sol','default':True}]):
            response=self.client.put('/harness/api/team',json={'engine':'codex','scope':'both'},headers={'origin':'http://testserver'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.state.team(),self.state.team('squad'))
        self.assertEqual(len(yaml.safe_load((self.root/'config.yaml').read_text())['models']),1)
        self.assertTrue(all(a['model']=='inherit' for a in yaml.safe_load((self.root/'config.yaml').read_text())['subagents']['custom_agents'].values()))
        self.assertEqual(set(self.client.get('/harness/api/catalog').json()['connections']),{'codex','gemini','deepseek','openai'})

    def test_text_only_model_does_not_activate_a_nonfunctional_team(self):
        original=(self.root/'config.yaml').read_bytes()
        self.tools_supported=False
        response=self.save()
        self.assertEqual(response.status_code,400)
        self.assertIn('function calling',response.text)
        self.assertEqual((self.root/'config.yaml').read_bytes(),original)

    def test_completion_token_api_is_detected_and_saved_without_changing_workers(self):
        self.assertEqual(self.save().status_code,200)
        original=self.state.team('squad')
        response=self.save(scope='coordinator',base_url=self.base+'/completion-token')
        self.assertEqual(response.status_code,200,response.text)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertEqual(credentials['token_limit_param'],'max_completion_tokens')
        self.assertEqual(self.state.team('squad'),original)
        self.assertIn('max_completion_tokens',self.requests[-1][2])

    def test_thinking_only_model_tool_choice_fallback_is_detected_saved_and_reused(self):
        response=self.save(base_url=self.base+'/required-choice');self.assertEqual(response.status_code,200,response.text)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertEqual(credentials['tool_choice'],'required')
        self.assertEqual(credentials['token_limit_param'],'max_tokens')
        checks=[r[2] for r in self.requests if r[0]=='POST' and any(t.get('function',{}).get('name')=='righaven_connection_check' for t in r[2].get('tools',[]))]
        self.assertEqual(len(checks),3)
        self.assertTrue(all(isinstance(c['tool_choice'],dict) for c in checks[:2]))
        self.assertEqual(checks[2]['tool_choice'],'required')
        result=self.save(api_key=None,base_url=profile['base_url'],connection_id=profile['connection_id'],model='Acme/Model-Y')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['team']['connection_id'],profile['connection_id'])

    def test_provider_rejecting_any_explicit_tool_choice_falls_back_to_omission(self):
        response=self.save(base_url=self.base+'/auto-choice');self.assertEqual(response.status_code,200,response.text)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertEqual(credentials['tool_choice'],'auto')
        self.assertEqual(credentials['token_limit_param'],'max_tokens')
        checks=[r[2] for r in self.requests if r[0]=='POST' and any(t.get('function',{}).get('name')=='righaven_connection_check' for t in r[2].get('tools',[]))]
        self.assertEqual(len(checks),5)
        self.assertNotIn('tool_choice',checks[-1])

    def test_reasoning_model_is_detected_and_saved_in_connection_credentials(self):
        self.assertEqual(self.save().status_code,200)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertFalse(credentials['reasoning'])
        response=self.save(api_key='fixture-reasoning-key',base_url=self.base+'/reasoning');self.assertEqual(response.status_code,200,response.text)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertTrue(credentials['reasoning'])

    def test_vision_support_is_probed_and_saved_in_connection_credentials(self):
        self.assertEqual(self.save().status_code,200)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertTrue(credentials['vision'])
        response=self.save(api_key='fixture-novision-key',base_url=self.base+'/no-vision');self.assertEqual(response.status_code,200,response.text)
        profile=self.state.team()
        credentials=json.loads(self.state.custom_connection_path(profile['connection_id']).read_text())
        self.assertFalse(credentials['vision'])

    def worker_run_with_previews(self, credentials):
        from righaven import deepseek,openai_compatible
        from righaven.handoff import validate_handoff
        import base64,test_deepseek
        output=self.root/'output';(output/'work').mkdir(parents=True)
        previews=output/'previews';previews.mkdir()
        (previews/'pagina-01.png').write_bytes(base64.b64decode(openai_compatible.VISION_PROBE_PNG))
        self.worker_manifest={'task':'Report','source_files':[],'output_files':[str(output/'report.txt')],
            'checks':[{'name':'Content','status':'passed','evidence':'Verified report'}],'warnings':[],
            'delivery':test_deepseek.report_delivery(output/'report.txt')}
        creds=self.root/'api.json';creds.write_text(json.dumps(credentials))
        def path(value):return creds if value=='/credentials/api.json' else Path(value)
        with patch.object(openai_compatible,'Path',side_effect=path),patch.object(deepseek,'Path',side_effect=path),patch.object(deepseek,'validate_handoff',side_effect=lambda folder,workspace,**kwargs:validate_handoff(folder,self.root,**kwargs)):
            message=openai_compatible.run('Acme/Model-X','Produce report',output,30)
        self.assertIn('Consegna registrata',message)
        return [r[2] for r in self.requests if r[0]=='POST']

    @staticmethod
    def has_image_parts(payload):
        return any(isinstance(m.get('content'),list) and any(isinstance(c,dict) and c.get('type')=='image_url' for c in m['content']) for m in payload['messages'])

    def test_worker_shows_new_previews_to_vision_models(self):
        posts=self.worker_run_with_previews({'api_key':'fixture-private-key','base_url':self.base,'vision':True})
        self.assertTrue(any(self.has_image_parts(p) for p in posts))

    def test_worker_without_vision_never_sends_images(self):
        posts=self.worker_run_with_previews({'api_key':'fixture-private-key','base_url':self.base,'vision':False})
        self.assertTrue(posts)
        self.assertTrue(all(not self.has_image_parts(p) for p in posts))

    def test_worker_retries_transient_provider_failures_before_completing(self):
        posts=self.worker_run_with_previews({'api_key':'fixture-private-key','base_url':self.base+'/flaky'})
        self.assertEqual(self.flaky,2)
        self.assertTrue(any('/flaky/' in r[1] for r in self.requests if r[0]=='POST'))

    def test_worker_raises_token_budget_for_reasoning_models(self):
        from righaven import deepseek,openai_compatible
        from righaven.handoff import validate_handoff
        import test_deepseek
        output=self.root/'output';(output/'work').mkdir(parents=True)
        self.worker_manifest={'task':'Report','source_files':[],'output_files':[str(output/'report.txt')],
            'checks':[{'name':'Content','status':'passed','evidence':'Verified report'}],'warnings':[],
            'delivery':test_deepseek.report_delivery(output/'report.txt')}
        creds=self.root/'api.json';creds.write_text(json.dumps({'api_key':'fixture-private-key','base_url':self.base,'reasoning':True}))
        def path(value):return creds if value=='/credentials/api.json' else Path(value)
        with patch.object(openai_compatible,'Path',side_effect=path),patch.object(deepseek,'Path',side_effect=path),patch.object(deepseek,'validate_handoff',side_effect=lambda folder,workspace,**kwargs:validate_handoff(folder,self.root,**kwargs)):
            message=openai_compatible.run('Acme/Model-X','Produce report',output,30)
        self.assertIn('Consegna registrata',message)
        posts=[r[2] for r in self.requests if r[0]=='POST']
        self.assertTrue(posts)
        self.assertTrue(all(p.get('max_tokens',0)>=16384 for p in posts))

    def test_worker_downgrades_forced_tool_choice_for_thinking_only_providers(self):
        from righaven import deepseek,openai_compatible
        from righaven.handoff import validate_handoff
        import test_deepseek
        output=self.root/'output';(output/'work').mkdir(parents=True)
        self.worker_manifest={'task':'Report','source_files':[],'output_files':[str(output/'report.txt')],
            'checks':[{'name':'Content','status':'passed','evidence':'Verified report'}],'warnings':[],
            'delivery':test_deepseek.report_delivery(output/'report.txt')}
        creds=self.root/'api.json';creds.write_text(json.dumps({'api_key':'fixture-private-key','base_url':self.base+'/required-choice','tool_choice':'required'}))
        def path(value):return creds if value=='/credentials/api.json' else Path(value)
        with patch.object(deepseek,'MAX_TURNS',2),patch.object(openai_compatible,'Path',side_effect=path),patch.object(deepseek,'Path',side_effect=path),patch.object(deepseek,'validate_handoff',side_effect=lambda folder,workspace,**kwargs:validate_handoff(folder,self.root,**kwargs)):
            message=openai_compatible.run('Acme/Model-X','Produce report',output,30)
        self.assertIn('Consegna registrata',message)
        posts=[r[2] for r in self.requests if r[0]=='POST']
        self.assertTrue(all(not isinstance(p.get('tool_choice'),dict) for p in posts))
        self.assertTrue(any(p.get('tool_choice')=='required' for p in posts))

    def test_worker_omits_forced_tool_choice_when_provider_rejects_it(self):
        from righaven import deepseek,openai_compatible
        from righaven.handoff import validate_handoff
        import test_deepseek
        output=self.root/'output';(output/'work').mkdir(parents=True)
        self.worker_manifest={'task':'Report','source_files':[],'output_files':[str(output/'report.txt')],
            'checks':[{'name':'Content','status':'passed','evidence':'Verified report'}],'warnings':[],
            'delivery':test_deepseek.report_delivery(output/'report.txt')}
        creds=self.root/'api.json';creds.write_text(json.dumps({'api_key':'fixture-private-key','base_url':self.base+'/auto-choice','tool_choice':'auto'}))
        def path(value):return creds if value=='/credentials/api.json' else Path(value)
        with patch.object(deepseek,'MAX_TURNS',2),patch.object(openai_compatible,'Path',side_effect=path),patch.object(deepseek,'Path',side_effect=path),patch.object(deepseek,'validate_handoff',side_effect=lambda folder,workspace,**kwargs:validate_handoff(folder,self.root,**kwargs)):
            message=openai_compatible.run('Acme/Model-X','Produce report',output,30)
        self.assertIn('Consegna registrata',message)
        posts=[r[2] for r in self.requests if r[0]=='POST']
        self.assertTrue(all('tool_choice' not in p for p in posts))

    def test_worker_uses_real_custom_http_tools_and_validates_handoff(self):
        from righaven import deepseek,openai_compatible
        from righaven.handoff import validate_handoff
        import test_deepseek
        output=self.root/'output';(output/'work').mkdir(parents=True)
        self.worker_manifest={'task':'Report','source_files':[],'output_files':[str(output/'report.txt')],
            'checks':[{'name':'Content','status':'passed','evidence':'Verified report'}],'warnings':[],
            'delivery':test_deepseek.report_delivery(output/'report.txt')}
        creds=self.root/'api.json';creds.write_text(json.dumps({'api_key':'fixture-private-key','base_url':self.base+'/completion-token','token_limit_param':'max_completion_tokens'}))
        def path(value):return creds if value=='/credentials/api.json' else Path(value)
        with patch.object(openai_compatible,'Path',side_effect=path),patch.object(deepseek,'Path',side_effect=path),patch.object(deepseek,'validate_handoff',side_effect=lambda folder,workspace,**kwargs:validate_handoff(folder,self.root,**kwargs)):
            message=openai_compatible.run('Acme/Model-X','Produce report',output,30)
        self.assertIn('Consegna registrata',message)
        self.assertEqual((output/'report.txt').read_text(),'verified')
        self.assertTrue((output/'handoff.json').is_file())
        self.assertTrue(all('thinking' not in r[2] for r in self.requests if r[0]=='POST'))
        self.assertTrue(all('max_completion_tokens' in r[2] and 'max_tokens' not in r[2] for r in self.requests if r[0]=='POST'))

    @unittest.skipIf(HarnessCompatibleChatModel is None,'Requires pinned Gateway OpenAI SDK')
    def test_actual_coordinator_sdk_and_streaming_use_selected_private_connection(self):
        self.assertEqual(self.save(scope='coordinator').status_code,200)
        model=HarnessCompatibleChatModel(connection_id=self.state.team()['connection_id'],model='Acme/Model-X',timeout=10)
        self.assertEqual(model.invoke('Hello').content,'OK')
        self.assertEqual(''.join(chunk.content for chunk in model.stream('Hello')),'OK')
        from righaven_core.config.app_config import AppConfig
        config=AppConfig.from_file(str(self.root/'config.yaml'))
        self.assertEqual(config.models[0].model,'Acme/Model-X')
        from righaven_core.models.factory import create_chat_model
        routed=create_chat_model('rh-codex',app_config=config,attach_tracing=False)
        self.assertEqual(routed.invoke('Hello').content,'OK')
