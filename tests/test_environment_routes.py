"""Genuine Gateway authorization boundaries; native CRUD also runs in ci_http."""
import os, unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
try:
    from app.gateway.authz import AuthContext
    from righaven_core.runtime.user_context import set_current_user,reset_current_user
    from righaven import environment_routes as routes,version_routes
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    routes=None


@unittest.skipIf(routes is None,'Requires pinned Gateway image')
class EnvironmentRouteTests(unittest.TestCase):
    def test_new_latest_release_keeps_verified_environment_ready_until_user_updates(self):
        agent=SimpleNamespace(name='docs')
        profile={'name':'docs','tools':['d2'],'deployment':{'mode':'preload'}}
        old={'id':'a'*64,'status':'ready','tools':['d2'],'version_names':{'d2':'v1'}}
        selected={'d2':'latest'}
        with patch.object(routes.profiles,'profile',return_value=profile), \
             patch.object(routes.profiles,'preloaded_tools',return_value=['d2']), \
             patch.object(routes.runtimes,'enabled',return_value=True), \
             patch('righaven.tool_versions.selections',return_value=selected), \
             patch('righaven.tool_versions.resolved',return_value={'d2':{'revision':'new'}}), \
             patch('righaven.state.team',return_value={'engine':'codex'}), \
             patch.object(routes.runtimes,'available',return_value={'id':'b'*64,'status':'on_demand','tools':['d2']}), \
             patch.object(routes.preparation,'read',return_value={'ready_id':'a'*64,'selection':selected}), \
             patch.object(routes.runtimes,'read',return_value=old), \
             patch.object(routes.runtimes,'image_exists',return_value=True), \
             patch.object(routes.preparation,'snapshot',return_value=None):
            result=routes.summary('owner',agent)
        self.assertEqual(result['runtime']['status'],'ready')
        self.assertTrue(result['runtime']['update_available'])
        self.assertEqual(result['runtime']['requested_id'],'b'*64)

    def test_native_config_loads_owner_scoped_soul_without_assuming_http_response_fields(self):
        from righaven_core.config.agents_config import AgentConfig
        config=AgentConfig(name='preloaded',description='Purpose',skills=[])
        self.assertFalse(hasattr(config,'soul'))
        with patch.object(routes.profiles,'resolve_skills',return_value={'skills':[],'tools':[],'disabled':[]}),patch.object(routes.profiles,'preferences',return_value={}),patch('righaven_core.config.agents_config.load_agent_soul',return_value='Keep editable sources') as load:
            first=routes.profiles.profile('owner',config)
            self.assertEqual(first['instructions'],'Keep editable sources')
            load.assert_called_once_with('preloaded',user_id='owner')
            load.return_value='Changed method'
            self.assertNotEqual(first['revision'],routes.profiles.profile('owner',config)['revision'])

    def test_one_broken_preload_does_not_prevent_gateway_or_other_profiles_from_starting(self):
        import tempfile,threading
        from pathlib import Path
        from righaven import state,tool_versions,environment_transfers
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'users/owner').mkdir(parents=True)
            def current(user,agent):
                if agent.name=='broken':raise AttributeError('incompatible profile')
                return {'runtime':{'status':'ready','id':'a'*64},'selected_versions':{}}
            with patch.object(state,'STATE',root/'state'),patch('righaven_core.config.paths.get_paths',return_value=SimpleNamespace(base_dir=root)),patch('righaven_core.config.agents_config.load_agent_config',side_effect=lambda name,**kw:SimpleNamespace(name=name)),patch.object(routes.runtimes,'enabled',return_value=True),patch.object(routes.runtimes,'reconcile'),patch.object(routes.runtimes,'STOPPING',threading.Event()),patch.object(environment_transfers,'recover'),patch.object(tool_versions,'recover_jobs'),patch.object(routes.profiles,'preferences',return_value={'broken':{'mode':'preload'},'valid':{'mode':'preload'}}),patch.object(routes,'summary',side_effect=current),patch.object(routes,'schedule') as schedule,self.assertLogs('righaven.environment_routes',level='ERROR'):
                routes.preload_startup()
                schedule.assert_not_called()
                self.assertEqual(routes.preparation.read('owner','broken')['phase'],'failed')
                self.assertEqual(routes.preparation.read('owner','valid')['phase'],'ready')

    def test_terminal_start_accepts_legacy_empty_body_and_validates_window_identity(self):
        from pydantic import ValidationError
        self.assertIsNone(routes.TerminalOpen.model_validate({}).client_id)
        self.assertIsNone(routes.TerminalOpen.model_validate({'client_id':None}).client_id)
        self.assertEqual(routes.TerminalOpen.model_validate({'client_id':'a'*32}).client_id,'a'*32)
        with self.assertRaises(ValidationError):routes.TerminalOpen.model_validate({'client_id':'invalid'})

    def test_permission_checks_apply_to_all_management_paths(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app=FastAPI();app.include_router(routes.router);app.include_router(version_routes.router)
        @app.middleware('http')
        async def authenticate(request,call_next):
            identity=request.headers.get('X-Test-User')
            user=SimpleNamespace(id=identity,system_role='user') if identity else None
            request.state.auth=AuthContext(user,[])
            request.state.user=user
            token=set_current_user(user)
            try:return await call_next(request)
            finally:reset_current_user(token)
        with TestClient(app) as client:
            for user,code in ((None,401),('no-permission',403)):
                headers={'X-Test-User':user} if user else {}
                for method,path in [('POST','/resources/rebalance'),('GET','/resources/settings'),('PUT','/resources/settings'),('GET',''),('POST',''),('POST','/prepare-preloaded'),('POST','/test/prepare'),('POST','/test/cancel'),('DELETE','/test/cache'),('GET','/test/log'),('GET','/test/export'),('POST','/test/software-export'),('POST','/test/software-import'),('POST','/test/terminal'),('POST','/terminal-clients/'+('a'*32)+'/close'),('POST','/terminals/'+('a'*32)+'/close'),('GET','/terminals/'+('a'*32)+'/status'),('POST','/terminals/'+('a'*32)+'/input'),('DELETE','/terminals/'+('a'*32)),('POST','/terminals/'+('a'*32)+'/resize'),('GET','/transfers/'+('a'*32)+'/status'),('GET','/transfers/'+('a'*32)+'/download')]:
                    body={'name':'test','display_name':'Test','purpose':'Test scope','skills':[]} if path=='' and method=='POST' else {'text':'echo ok'} if path.endswith('/input') else {'cols':80,'rows':24} if path.endswith('/resize') else {'mode':'auto','cpus':1.5,'memory_mib':1536,'max_workers':2} if path=='/resources/settings' and method=='PUT' else None
                    reply=client.request(method,'/api/harness/environments'+path,headers=headers,json=body)
                    self.assertEqual(reply.status_code,code,reply.text)
                for method,path,body in [('GET','',None),('GET','/d2/releases',None),('POST','',{'tool':'d2','version':'latest'}),('PUT','/default',{'tool':'d2','revision':'latest'})]:
                    reply=client.request(method,'/api/harness/tool-versions'+path,headers=headers,json=body)
                    self.assertEqual(reply.status_code,code,reply.text)


    def test_only_admin_can_change_the_shared_budget_from_environments(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven import runtime_settings
        app=FastAPI();app.include_router(routes.router)
        @app.middleware('http')
        async def authenticate(request,call_next):
            user=SimpleNamespace(id='owner',system_role='user')
            request.state.auth=AuthContext(user,['agents:read','agents:write'])
            request.state.user=user
            token=set_current_user(user)
            try:return await call_next(request)
            finally:reset_current_user(token)
        with patch('app.gateway.deps.is_admin_user',new=AsyncMock(return_value=False)) as admin,patch.object(runtime_settings,'save',return_value={'saved':True}) as save,patch.object(runtime_settings,'read',return_value={'settings':{'max_workers':2}}),TestClient(app) as client:
            response=client.get('/api/harness/environments/resources/settings')
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
            payload={'mode':'manual','cpus':2,'memory_mib':3072,'max_workers':3,'model_wait_seconds':120}
            url='/api/harness/environments/resources/settings'
            self.assertEqual(client.post('/api/harness/environments/resources/rebalance',headers={'Origin':'http://testserver'}).status_code,403)
            self.assertEqual(client.put(url,json=payload,headers={'Origin':'http://testserver'}).status_code,403)
            save.assert_not_called();admin.return_value=True
            self.assertEqual(client.put(url,json=payload,headers={'Origin':'https://other.example'}).status_code,403)
            save.assert_not_called()
            self.assertEqual(client.put(url,json=payload,headers={'Origin':'http://testserver'}).status_code,200)
            save.assert_called_once_with(payload)
            with patch('righaven.resource_budget.BUDGET.rebalance',return_value={'updated':1,'unchanged':0,'pending':0}) as rebalance:
                response=client.post('/api/harness/environments/resources/rebalance',headers={'Origin':'http://testserver'})
                self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['updated'],1)
                rebalance.assert_called_once()
            self.assertEqual(client.put(url,json={**payload,'max_workers':9}).status_code,422)
            # An ordinary environment may legitimately be named "resources".
            # Resource settings must not shadow its native profile update.
            with patch.object(routes,'write_definition',new=AsyncMock(return_value={'name':'resources'})) as write:
                definition={'name':'resources','display_name':'Resources','purpose':'Custom environment','skills':[]}
                reply=client.put('/api/harness/environments/resources',json=definition,headers={'Origin':'http://testserver'})
                self.assertEqual(reply.status_code,200,reply.text)
                write.assert_awaited_once()

    def test_restart_keeps_ready_preloads_and_only_restores_missing_images_without_refresh(self):
        import tempfile,threading
        from pathlib import Path
        from righaven import state,tool_versions,environment_transfers
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'users/owner').mkdir(parents=True)
            def current(user,agent):
                return {'runtime':{'status':'ready' if agent.name=='ready' else 'on_demand','id':'a'*64},'selected_versions':{'d2':'latest'}}
            with patch.object(state,'STATE',root/'state'),patch('righaven_core.config.paths.get_paths',return_value=SimpleNamespace(base_dir=root)),patch('righaven_core.config.agents_config.load_agent_config',side_effect=lambda name,**kw:SimpleNamespace(name=name)),patch.object(routes.runtimes,'enabled',return_value=True),patch.object(routes.runtimes,'reconcile'),patch.object(routes.runtimes,'STOPPING',threading.Event()),patch.object(environment_transfers,'recover'),patch.object(tool_versions,'recover_jobs'),patch.object(routes.profiles,'preferences',return_value={'ready':{'mode':'preload'},'missing':{'mode':'preload'},'on-demand':{'mode':'on_demand'}}),patch.object(routes,'summary',side_effect=current),patch.object(routes,'schedule') as schedule:
                routes.preload_startup()
                schedule.assert_called_once_with('owner','missing',refresh_versions=False,trigger='startup')
                self.assertEqual(routes.preparation.read('owner','ready')['phase'],'ready')

    def test_owner_identity_is_forwarded_to_native_agent_listing(self):
        import tempfile
        from pathlib import Path
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven import state
        app=FastAPI();app.include_router(routes.router);app.include_router(version_routes.router)
        @app.middleware('http')
        async def authenticate(request,call_next):
            user=SimpleNamespace(id=request.headers['X-Test-User'],system_role='user')
            request.state.auth=AuthContext(user,['agents:read','agents:write'])
            request.state.user=user
            token=set_current_user(user)
            try:return await call_next(request)
            finally:reset_current_user(token)
        async def native(request):
            from righaven_core.runtime.user_context import get_effective_user_id
            self.assertEqual(get_effective_user_id(),request.headers['X-Test-User'])
            return []
        with tempfile.TemporaryDirectory() as temp,patch.object(state,'STATE',Path(temp)),patch.object(routes,'native_agents',side_effect=native),patch.object(routes.profiles,'skill_inventory',return_value=[]),patch.object(routes.runtimes,'enabled',return_value=False),TestClient(app) as client:
            for owner in ('one','two'):
                r=client.get('/api/harness/environments',headers={'X-Test-User':owner})
                self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.headers['Cache-Control'],'no-store')
                self.assertEqual(r.json()['environments'],[])
                self.assertGreaterEqual(len(r.json()['presets']),9)

    def test_invalid_native_dependencies_return_an_actionable_conflict(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app=FastAPI();app.include_router(routes.router);app.include_router(version_routes.router)
        @app.middleware('http')
        async def authenticate(request,call_next):
            user=SimpleNamespace(id='owner',system_role='user')
            request.state.auth=AuthContext(user,['agents:read','agents:write'])
            request.state.user=user
            token=set_current_user(user)
            try:return await call_next(request)
            finally:reset_current_user(token)
        with patch.object(routes,'native_agent',new=AsyncMock(return_value=object())),patch.object(routes,'summary',side_effect=ValueError('Dipendenza disabilitata')),patch.object(routes.runtimes,'enabled',return_value=True),patch.object(routes,'schedule') as schedule,TestClient(app) as client:
            for method,tail in [('POST','prepare'),('GET','log'),('DELETE','cache')]:
                response=client.request(method,'/api/harness/environments/fixture/'+tail,headers={'Origin':'http://testserver'})
                self.assertEqual(response.status_code,409,response.text)
                self.assertIn('disabilitata',response.json()['detail'])
            schedule.assert_not_called()

    def test_regular_agent_writer_cannot_replace_the_shared_software_cache(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app=FastAPI();app.include_router(routes.router);app.include_router(version_routes.router)
        @app.middleware('http')
        async def authenticate(request,call_next):
            user=SimpleNamespace(id='owner',system_role='user')
            request.state.user=user;request.state.auth=AuthContext(user,['agents:read','agents:write'])
            token=set_current_user(user)
            try:return await call_next(request)
            finally:reset_current_user(token)
        with patch.object(routes,'native_agent',new=AsyncMock()) as agent,TestClient(app) as client:
            response=client.post('/api/harness/environments/test/software-import',headers={'Origin':'http://testserver'},content=b'not read before admin check')
            self.assertEqual(response.status_code,403,response.text)
            for method,tail,body in [('POST','',{'tool':'provider-agy','version':'latest'}),('PUT','/default',{'tool':'d2','revision':'latest'})]:
                result=client.request(method,'/api/harness/tool-versions'+tail,headers={'Origin':'http://testserver'},json=body)
                self.assertEqual(result.status_code,403,result.text)

            self.assertIn('amministratore',response.json()['detail'])
            agent.assert_not_called()

    def test_a_new_preload_request_is_not_lost_while_the_previous_recipe_finishes(self):
        import threading
        from righaven import docker_runtime
        targets=[];executions=[]
        def thread(**kwargs):
            return SimpleNamespace(start=lambda:targets.append(kwargs['target']))
        def ensure(*args,**kwargs):
            executions.append(args)
            if len(executions)==1:routes.schedule('owner','fixture',reschedule=True)
            return {'id':'a'*64}
        with patch.object(routes.runtimes,'PREPARING',set()),patch.object(routes.runtimes,'PREPARATION_CONTROL',{}),patch.object(routes.runtimes,'STOPPING',threading.Event()),patch.object(docker_runtime,'BUILD_LOCK',threading.Lock()),patch('righaven_core.config.agents_config.load_agent_config',return_value=SimpleNamespace(skills=['skill-d2'])),patch('righaven.capability_policy.native_policy',return_value={'allowed':['d2']}),patch.object(routes.profiles,'resolve_skills',return_value={'tools':['d2']}),patch.object(routes.profiles,'preferences',return_value={}),patch.object(routes.runtimes,'recipe',return_value=('a'*64,{})),patch.object(routes.runtimes,'ensure',side_effect=ensure),patch.object(routes.threading,'Thread',side_effect=thread):
            routes.schedule('owner','fixture');self.assertEqual(len(targets),1)
            targets[0]();self.assertEqual(len(targets),2)
            targets[1]();self.assertEqual(len(executions),2)
            self.assertFalse(routes.runtimes.PREPARING)

    def test_personal_requirements_use_frontmatter_accepted_by_the_native_installer(self):
        import tempfile
        from pathlib import Path
        from righaven_core.skills.validation import validate_skill_frontmatter_text
        text='---\nname: native-method\ndescription: Editable diagram method\nmetadata:\n  righaven-tools: [d2]\n---\nPreserve and verify the diagram.\n'
        valid,message,name=validate_skill_frontmatter_text(text)
        self.assertTrue(valid,message)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);(path/'SKILL.md').write_text(text)
            self.assertEqual(routes.profiles.skill_requirements(SimpleNamespace(name=name,skill_dir=path)),['d2'])

    def test_preload_controller_retries_after_foreground_priority_without_a_second_user_request(self):
        import threading,time
        from righaven import docker_runtime
        from righaven.resource_slot import ResourceSlot
        started=threading.Event();finished=threading.Event();executions=[];slot=ResourceSlot(idle_seconds=.01)
        def ensure(*args,**kwargs):
            with routes.runtimes.preparation_slot(slot,True,kwargs['cancel'],None,background=True):
                executions.append(args)
                if len(executions)==1:
                    started.set();until=time.monotonic()+3
                    while not kwargs['cancel'].is_set() and time.monotonic()<until:time.sleep(.005)
                    self.assertTrue(kwargs['cancel'].deferred)
                    raise routes.runtimes.PreparationDeferred('Yield for foreground')
                finished.set()
                return {'id':'a'*64}
        with patch.object(routes.runtimes,'PREPARING',set()),patch.object(routes.runtimes,'PREPARATION_CONTROL',{}),patch.object(routes.runtimes,'STOPPING',threading.Event()),patch.object(docker_runtime,'BUILD_LOCK',slot),patch('righaven_core.config.agents_config.load_agent_config',return_value=SimpleNamespace(skills=['skill-d2'])),patch('righaven.capability_policy.native_policy',return_value={'allowed':['d2']}),patch.object(routes.profiles,'resolve_skills',return_value={'tools':['d2']}),patch.object(routes.profiles,'preferences',return_value={}),patch.object(routes.runtimes,'recipe',return_value=('a'*64,{})),patch.object(routes.runtimes,'ensure',side_effect=ensure):
            routes.schedule('owner','fixture');self.assertTrue(started.wait(2))
            self.assertTrue(slot.acquire(timeout=2))
            try:self.assertFalse(finished.is_set())
            finally:slot.release()
            self.assertTrue(finished.wait(2))
            until=time.monotonic()+2
            while routes.runtimes.PREPARING and time.monotonic()<until:time.sleep(.005)
            self.assertEqual(len(executions),2);self.assertFalse(routes.runtimes.PREPARING)
            self.assertEqual(routes.runtimes.PREPARATION_CONTROL[('owner','fixture')]['error'],'')

    def test_version_phase_is_visible_and_repeated_prepare_does_not_create_a_second_job(self):
        import tempfile,threading,time
        from pathlib import Path
        from righaven import state,docker_runtime,tool_versions,environment_preparation
        from righaven.resource_slot import ResourceSlot
        entered=threading.Event();release=threading.Event();owner=('owner','docs')
        agent=SimpleNamespace(name='docs',skills=['skill-d2'])
        def resolve(value,**kwargs):
            if not kwargs.get('wait'):return {}
            kwargs['on_progress'](phase='checking_versions',tool='d2',version='v0.9.0',index=1,total=1)
            entered.set();release.wait(2);return {}
        with tempfile.TemporaryDirectory() as temporary,patch.object(state,'STATE',Path(temporary)),patch.object(routes.runtimes,'PREPARING',set()),patch.object(routes.runtimes,'PREPARATION_CONTROL',{}),patch.object(routes.runtimes,'STOPPING',threading.Event()),patch.object(docker_runtime,'BUILD_LOCK',ResourceSlot(idle_seconds=0)),patch('righaven_core.config.agents_config.load_agent_config',return_value=agent),patch.object(routes.profiles,'resolve_skills',return_value={'tools':['d2']}),patch.object(routes.profiles,'preferences',return_value={'docs':{'mode':'preload'}}),patch('righaven.capability_policy.native_policy',return_value={'allowed':['d2'],'blocked':[]}),patch.object(state,'team',return_value={'engine':'deepseek'}),patch.object(tool_versions,'selections',return_value={}),patch.object(tool_versions,'resolved',side_effect=resolve),patch.object(routes.runtimes,'recipe',return_value=('a'*64,{'tools':['d2']})),patch.object(routes.runtimes,'ensure',return_value={'id':'a'*64}) as ensure,patch.object(routes.runtimes,'available',return_value={'status':'on_demand','tools':['d2']}),patch.object(routes.runtimes,'enabled',return_value=True),patch.object(routes.profiles,'profile',return_value={'name':'docs','tools':['d2'],'deployment':{'mode':'preload'}}):
            routes.schedule(*owner)
            try:
                self.assertTrue(entered.wait(2))
                current=routes.summary(owner[0],agent)
                self.assertEqual(current['runtime']['status'],'checking_versions')
                self.assertEqual(current['preparation']['tool'],'d2')
                routes.schedule(*owner)
                self.assertFalse(routes.runtimes.PREPARATION_CONTROL[owner]['reschedule'])
            finally:release.set()
            until=time.monotonic()+2
            while owner in routes.runtimes.PREPARING and time.monotonic()<until:time.sleep(.01)
            self.assertNotIn(owner,routes.runtimes.PREPARING)
            self.assertEqual(routes.runtimes.PREPARATION_CONTROL[owner]['error'],'')
            self.assertEqual(ensure.call_count,1)
            self.assertEqual(environment_preparation.read(*owner)['phase'],'ready')

    def test_running_delegate_batch_observes_an_increased_live_limit(self):
        import json,threading
        from righaven import tools
        from righaven.worker_slots import WorkerSlots
        limits={'cpus':4,'memory_mib':4096,'max_workers':1}
        slots=WorkerSlots();first=threading.Event();second=threading.Event();release=threading.Event()
        admitted=[];lock=threading.Lock();results=[]
        def delegate(**kwargs):
            if not slots.acquire(timeout=3):raise RuntimeError('Admission timeout')
            try:
                with lock:
                    admitted.append(kwargs['task']);first.set()
                    if len(admitted)>=2:second.set()
                if not release.wait(3):raise RuntimeError('Completion timeout')
                return json.dumps({'ok':True})
            finally:slots.release()
        assignments=json.dumps([{'agent':'workspace','role_id':'role'+str(i),'task':'task'+str(i)} for i in range(3)])
        with patch('righaven.runtime_settings.effective',side_effect=lambda:dict(limits)),patch.object(tools.harness_delegate,'func',side_effect=delegate):
            thread=threading.Thread(target=lambda:results.append(json.loads(tools.harness_delegate_batch.func(assignments_json=assignments,runtime=None))))
            thread.start()
            try:
                self.assertTrue(first.wait(1));self.assertFalse(second.wait(.1))
                limits['max_workers']=2
                self.assertTrue(second.wait(2),'An existing batch retained its old executor limit')
            finally:release.set();thread.join(4)
            self.assertFalse(thread.is_alive());self.assertTrue(results[0]['ok']);self.assertEqual(len(results[0]['assignments']),3)

    def test_legacy_post_check_failure_is_not_presented_as_a_tool_failure(self):
        import tempfile
        from pathlib import Path
        from righaven import state,tool_versions
        agent=SimpleNamespace(name='3d',skills=['skill-pymeshlab'])
        old={'kind':'verification','tool':'pymeshlab','message':'pymeshlab: collaudo non superato.','failed_tools':[],'passed_tools':['pymeshlab']}
        runtime={'id':'a'*64,'status':'failed','tools':['pymeshlab'],'failure':old,'error':old['message']}
        with tempfile.TemporaryDirectory() as temporary,patch.object(state,'STATE',Path(temporary)),patch.object(routes.runtimes,'enabled',return_value=True),patch.object(routes.runtimes,'available',return_value=runtime),patch.object(routes.runtimes,'preparation_text',return_value='Installazione pymeshlab 2025.7.post1\nOK pymeshlab \n{"phase":"verified"}\n'),patch.object(routes.profiles,'profile',return_value={'name':'3d','tools':['pymeshlab'],'deployment':{'mode':'preload'}}),patch.object(tool_versions,'selections',return_value={}),patch.object(tool_versions,'resolved',return_value={}):
            value=routes.summary('owner',agent)
            self.assertEqual(value['runtime']['failure']['kind'],'publication')
            self.assertEqual(value['runtime']['failure']['tool'],'')
            self.assertIn('non è stato conservato',value['runtime']['failure']['details'])
            self.assertEqual(old['tool'],'pymeshlab')

    def test_global_version_changes_prepare_affected_preloads_but_respect_profile_pins(self):
        import tempfile
        from pathlib import Path
        from righaven import state
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'users/owner').mkdir(parents=True)
            preferences={'docs':{'mode':'preload'},'fixed':{'mode':'preload','tool_versions':{'d2':'builtin'}},'later':{'mode':'on_demand'}}
            with patch('righaven_core.config.paths.get_paths',return_value=SimpleNamespace(base_dir=root)),patch('righaven_core.config.agents_config.load_agent_config',return_value=SimpleNamespace(skills=['skill-d2'])),patch.object(routes.profiles,'preferences',return_value=preferences),patch.object(routes.profiles,'resolve_skills',return_value={'tools':['d2']}),patch.object(state,'team',return_value={'engine':'deepseek'}),patch.object(routes,'schedule') as schedule:
                self.assertEqual(routes.schedule_affected('d2'),1)
                schedule.assert_called_once_with('owner','docs',reschedule=True,trigger='version_change',trigger_tool='d2')
                schedule.reset_mock();self.assertEqual(routes.schedule_affected('calibre'),0);schedule.assert_not_called()
