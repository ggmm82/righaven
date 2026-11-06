"""Exercise the genuine Gateway ownership decorator in its built image."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

try:
    from app.gateway.authz import AuthContext
    from righaven_core.runtime.user_context import set_current_user, reset_current_user
    from righaven.progress_routes import router
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    router = None


@unittest.skipIf(router is None, 'Requires the pinned Gateway image')
class ProgressRouteTests(unittest.TestCase):
    def test_owner_can_read_after_reload_but_other_users_and_anonymous_cannot(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven.progress import create_job, update
        from righaven.projects import create_plan
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = create_job(root / 'owner/conversation', 'rh-job-123456abcdef', 'cadcraft', 'codex', 'fixture')
            update(path, 'creating', 'Creazione del sorgente modificabile')
            create_plan(root / 'owner/conversation', 'Tavola tecnica', [
                {'id': 'drawing', 'agent': 'cadcraft', 'goal': 'Disegno quotato', 'depends_on': []}])
            app = FastAPI()
            app.include_router(router)

            @app.middleware('http')
            async def fixture_auth(request, call_next):
                identity = request.headers.get('X-Test-User')
                user = SimpleNamespace(id=identity, system_role='user') if identity else None
                permissions = ['threads:read', 'threads:write'] if identity != 'no-permission' else []
                request.state.auth = AuthContext(user, permissions)
                token = set_current_user(user)
                try:
                    return await call_next(request)
                finally:
                    reset_current_user(token)

            async def check_access(thread, user, require_existing=False):
                self.assertTrue(require_existing)
                return thread == 'conversation' and user == 'owner'
            store = SimpleNamespace(check_access=AsyncMock(side_effect=check_access))
            paths = SimpleNamespace(user_dir=lambda user_id: root / user_id, sandbox_user_data_dir=lambda thread, user_id: root / user_id / thread)
            with patch('app.gateway.deps.get_thread_store', return_value=store), \
                 patch('righaven.progress_routes.get_paths', return_value=paths), TestClient(app) as client:
                url = '/api/threads/conversation/harness-jobs'
                for attempt in range(2):
                    result = client.get(url, headers={'X-Test-User': 'owner'})
                    self.assertEqual(result.status_code, 200, result.text)
                    self.assertEqual(result.json()['jobs'][0]['summary'], 'Creazione del sorgente modificabile')
                    self.assertEqual(result.json()['project']['steps'][0]['agent'], 'cadcraft')
                    self.assertEqual(result.headers['cache-control'], 'no-store')
                self.assertEqual(client.get(url).status_code, 401)
                self.assertEqual(client.get(url, headers={'X-Test-User': 'other'}).status_code, 404)
                self.assertEqual(client.get(url, headers={'X-Test-User': 'no-permission'}).status_code, 403)
                self.assertEqual(client.get('/api/threads/missing/harness-jobs', headers={'X-Test-User': 'owner'}).status_code, 404)
                from righaven import state
                from righaven.task_staging import TaskStaging
                stage = TaskStaging(root/'state', root/'owner/conversation', 'cadcraft', 'rh-job-123456abcdef')
                stage.prepare(); (stage.output/'command.txt').write_text('private command')
                file_url = '/api/threads/conversation/harness-job-file'
                with patch.object(state, 'STATE', root/'state'):
                    params={'path':str(stage.logical/'command.txt')}
                    self.assertEqual(client.get(file_url,params=params).status_code,401)
                    self.assertEqual(client.get(file_url,params=params,headers={'X-Test-User':'other'}).status_code,404)
                    self.assertEqual(client.get(file_url,params=params,headers={'X-Test-User':'no-permission'}).status_code,403)
                    opened=client.get(file_url,params=params,headers={'X-Test-User':'owner'})
                    self.assertEqual(opened.status_code,200,opened.text)
                    self.assertEqual(opened.text,'private command')
                    self.assertEqual(opened.headers['x-content-type-options'],'nosniff')
                    self.assertEqual(client.get(file_url,params={'path':'/etc/passwd'},headers={'X-Test-User':'owner'}).status_code,404)
                guide_url = '/api/threads/conversation/harness-guide'
                self.assertEqual(client.get(guide_url).status_code, 401)
                self.assertEqual(client.get(guide_url, headers={'X-Test-User':'other'}).status_code, 404)
                self.assertEqual(client.get(guide_url, headers={'X-Test-User':'no-permission'}).status_code, 403)
                self.assertEqual(client.get(guide_url, headers={'X-Test-User':'owner'}).status_code, 409)
                from righaven import projects
                from righaven.source_packages import digest
                import json, io, zipfile
                workspace = root / 'owner/conversation'
                output = workspace / 'outputs/workspace/rh-job-222222222222'; output.mkdir(parents=True)
                product = output / 'result.txt'; product.write_text('Owner-only product')
                projects.execute_step(workspace, 'cadcraft', 'Tavola tecnica', 'drawing', lambda *a: json.dumps({
                    'ok':True, 'output_dir':str(output), 'handoff':{'output_files':[str(product)],'checks':[]},
                    'delivery_record':{'id':output.name,'title':'Tavola tecnica','technical_status':'passed',
                                      'files':[{'path':str(product),'role':'export','sha256':digest(product)}]}}), purpose='delivery')
                guide = client.get(guide_url, headers={'X-Test-User':'owner'})
                self.assertEqual(guide.status_code, 200, guide.text)
                self.assertEqual(guide.json()['delivery_id'], output.name)
                self.assertEqual(guide.headers['cache-control'], 'no-store')
                md = client.get(guide_url+'?format=markdown', headers={'X-Test-User':'owner'})
                self.assertIn('Guida del progetto', md.text)
                self.assertIn('attachment', md.headers['content-disposition'])
                zipped = client.get(guide_url+'?format=zip', headers={'X-Test-User':'owner'})
                self.assertEqual(zipped.status_code, 200, zipped.text if zipped.status_code != 200 else '')
                with zipfile.ZipFile(io.BytesIO(zipped.content)) as archive:
                    self.assertEqual(archive.read('File/result.txt'), b'Owner-only product')
                    self.assertIn('GUIDA-PROGETTO.md', archive.namelist())
                self.assertEqual(client.get(guide_url+'?format=zip', headers={'X-Test-User':'other'}).status_code, 404)
                self.assertEqual(client.get(guide_url+'?delivery_id=other', headers={'X-Test-User':'owner'}).status_code, 409)
                audit_url='/api/threads/conversation/harness-audit'
                self.assertEqual(client.get(audit_url).status_code,401)
                self.assertEqual(client.get(audit_url,headers={'X-Test-User':'other'}).status_code,404)
                audit=client.get(audit_url,headers={'X-Test-User':'owner'})
                self.assertEqual(audit.status_code,200)
                self.assertTrue(audit.json()['events'])
                export=client.get(audit_url+'?export=true',headers={'X-Test-User':'owner'})
                self.assertIn('text/csv',export.headers['content-type'])
                self.assertIn('timestamp_utc',export.text)
                control_url = '/api/threads/conversation/harness-control'
                self.assertEqual(client.put(control_url,json={'paused':True}).status_code,401)
                self.assertEqual(client.put(control_url,json={'paused':True},headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.put(control_url,json={'paused':True},headers={'X-Test-User':'owner'}).json()['user_control']['paused'],True)
                self.assertEqual(client.put(control_url,json={'paused':False},headers={'X-Test-User':'owner'}).json()['user_control']['paused'],False)
                finish_url='/api/threads/conversation/harness-deliver-now'
                self.assertEqual(client.post(finish_url).status_code,401)
                self.assertEqual(client.post(finish_url,headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.post(finish_url,headers={'X-Test-User':'no-permission'}).status_code,403)
                self.assertEqual(client.post(finish_url,headers={'X-Test-User':'owner','Origin':'https://unrelated.invalid'}).status_code,403)
                with patch('righaven.docker_runtime.request_finish',return_value={'closing':True}):
                    closed=client.post(finish_url,headers={'X-Test-User':'owner'})
                    self.assertEqual(closed.status_code,200,closed.text)
                    self.assertTrue(closed.json()['user_control']['deliver_now'])
                resumed=client.put(control_url,json={'paused':False},headers={'X-Test-User':'owner'})
                self.assertFalse(resumed.json()['user_control'].get('deliver_now',False))
                experience_url = '/api/threads/conversation/harness-experience'
                self.assertEqual(client.get(experience_url).status_code, 401)
                self.assertEqual(client.get(experience_url, headers={'X-Test-User':'other'}).status_code, 404)
                self.assertEqual(client.get(experience_url, headers={'X-Test-User':'no-permission'}).status_code, 403)
                self.assertEqual(client.get(experience_url, headers={'X-Test-User':'owner'}).json()['total'], 0)
                curate_url=experience_url+'/curate'
                self.assertEqual(client.post(curate_url).status_code,401)
                self.assertEqual(client.post(curate_url,headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.post(curate_url,headers={'X-Test-User':'no-permission'}).status_code,403)
                with patch('righaven.lesson_curation.generate') as generate:
                    empty=client.post(curate_url,headers={'X-Test-User':'owner'})
                    self.assertEqual(empty.status_code,200,empty.text)
                    self.assertEqual(empty.json()['curation']['status'],'no_sources')
                    generate.assert_not_called()
                with patch('righaven.lessons.pending',return_value=[{'id':'a'*64}]), \
                     patch('righaven.progress_routes.production_running',new=AsyncMock(return_value=True)), \
                     patch('righaven.lesson_curation.curate') as curate:
                    busy=client.post(curate_url,headers={'X-Test-User':'owner'})
                    self.assertEqual(busy.status_code,409)
                    curate.assert_not_called()
                import json
                from righaven.acceptance import fingerprint
                from righaven.state import atomic_json
                from langchain_core.messages import AIMessage
                observation={'source_thread':'conversation','status':'failed','criterion':'Resource links',
                    'method':'functional','evidence':'A linked resource was absent','tools':{},'corrections':[]}
                identifier=fingerprint(observation)
                library=root/'owner/righaven-experience';library.mkdir(exist_ok=True)
                atomic_json(library/(identifier+'.json'),{'id':identifier,'at':'2026-10-24T00:00:00Z','observation':observation})
                proposal={'source_ids':[identifier],'lesson':{'category':'production_method','title':'Check portable resources',
                    'applies_when':'A deliverable has linked resources','procedure':['Resolve links before delivery'],
                    'verification':['Reopen the transferred package'],'limits':'Not an aesthetic evaluation','tools':[]},
                    'impact':{'level':'unknown','basis':'hypothesis','reason':'A missing file suggests a check, not a measured improvement'}}
                model=SimpleNamespace(invoke=lambda messages:AIMessage(content=json.dumps({'proposals':[proposal],'dismissed':[]})))
                with patch('righaven.progress_routes.production_running',new=AsyncMock(return_value=False)), \
                     patch('righaven_core.models.create_chat_model',return_value=model) as factory:
                    saved=client.post(curate_url,headers={'X-Test-User':'owner'})
                    self.assertEqual(saved.status_code,200,saved.text)
                    self.assertEqual(saved.json()['curation']['saved'],1)
                    self.assertEqual(saved.json()['current_project']['lessons'],1)
                    self.assertFalse(saved.json()['lessons'][0]['accepted'])
                    self.assertEqual(factory.call_args.args[0],'rh-codex')
                self.assertEqual(client.post(experience_url+'/collect', headers={'X-Test-User':'other'}).status_code, 404)
                self.assertEqual(client.post(experience_url+'/collect', headers={'X-Test-User':'owner'}).status_code, 200)
                self.assertEqual(client.put(experience_url,json={'id':'a'*64,'excluded':True},headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.post(experience_url+'/prefer',json={'delivery_id':'rh-job-123456abcdef','note':'Preferenza personale'},headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.put(experience_url+'/lesson',json={'id':'a'*64,'accepted':True},headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.put(experience_url+'/lesson',json={'id':'a'*64,'accepted':True},headers={'X-Test-User':'owner'}).status_code,409)
                with patch('righaven.docker_runtime.request_stop',return_value={'requested':True}) as stop:
                    stop_url='/api/threads/conversation/harness-jobs/rh-job-123456abcdef/stop'
                    self.assertEqual(client.post(stop_url).status_code,401)
                    self.assertEqual(client.post(stop_url,headers={'X-Test-User':'other'}).status_code,404)
                    self.assertEqual(client.post(stop_url,headers={'X-Test-User':'owner'}).status_code,200)
                    stop.assert_called_once()
                from righaven.project_design import register
                design_source=root/'owner/conversation/outputs/idea.mmd';design_source.parent.mkdir(exist_ok=True);design_source.write_text('flowchart LR\n a --> b')
                register(root/'owner/conversation',[{'id':'idea','title':'Idea','tool':'mermaid','source_path':str(design_source)}],{'mermaid'})
                design_url='/api/threads/conversation/rh-designs/idea'
                self.assertEqual(client.get(design_url).status_code,401)
                self.assertEqual(client.get(design_url,headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.get(design_url,headers={'X-Test-User':'no-permission'}).status_code,403)
                self.assertEqual(client.get(design_url,headers={'X-Test-User':'owner'}).json()['revision'],1)
                payload={'revision':1,'source':'flowchart LR\n a --> c'}
                with patch('righaven.capability_policy.native_policy',return_value={'allowed':['mermaid']}):
                    self.assertEqual(client.post(design_url,headers={'X-Test-User':'other'},json=payload).status_code,404)
                    changed=client.post(design_url,headers={'X-Test-User':'owner'},json=payload)
                    self.assertEqual(changed.status_code,200,changed.text)
                    self.assertEqual(changed.json()['design']['revision'],2)
                    self.assertEqual(client.post(design_url,headers={'X-Test-User':'owner'},json=payload).status_code,409)
                with patch('righaven.capability_policy.native_policy',return_value={'allowed':[]}):
                    self.assertEqual(client.post(design_url,headers={'X-Test-User':'owner'},json={'revision':2,'source':'flowchart LR\n a --> d'}).status_code,409)
                direction_url = '/api/threads/conversation/harness-direction'
                direction = {'visual_approach': 'vector', 'instructions': 'Disegni modificabili'}
                self.assertEqual(client.put(direction_url,json=direction).status_code,401)
                self.assertEqual(client.put(direction_url,json=direction,headers={'X-Test-User':'other'}).status_code,404)
                self.assertEqual(client.put(direction_url,json=direction,headers={'X-Test-User':'no-permission'}).status_code,403)
                self.assertEqual(client.put(direction_url,json=direction,headers={'X-Test-User':'owner'}).status_code,200)
                self.assertEqual(client.get(url,headers={'X-Test-User':'owner'}).json()['project']['user_direction']['visual_approach'],'vector')
                self.assertEqual(client.put(direction_url,json={'visual_approach':'invalid'},headers={'X-Test-User':'owner'}).status_code,422)
                accept_url = '/api/threads/conversation/harness-delivery/accept'
                data = {'delivery_id': 'nonexistent'}
                self.assertEqual(client.post(accept_url, json=data).status_code, 401)
                self.assertEqual(client.post(accept_url, json=data, headers={'X-Test-User': 'other'}).status_code, 404)
                self.assertEqual(client.post(accept_url, json=data, headers={'X-Test-User': 'no-permission'}).status_code, 403)
                self.assertEqual(client.post(accept_url, json=data, headers={'X-Test-User': 'owner'}).status_code, 409)
