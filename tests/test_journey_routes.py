"""Real Gateway owner and permission checks for guided projects."""
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock,patch
try:
    from app.gateway.authz import AuthContext
    from righaven_core.runtime.user_context import set_current_user,reset_current_user
    from righaven.recipe_routes import journey_router, router as recipe_router
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    journey_router=None


@unittest.skipIf(journey_router is None,'Requires the native Gateway')
class JourneyRoutes(unittest.TestCase):
    def test_owner_start_reload_decision_scope_and_conflicting_revision(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven import projects,journeys,state
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=FastAPI();app.include_router(journey_router)
            @app.middleware('http')
            async def auth(request,call_next):
                identity=request.headers.get('X-Test-User');user=SimpleNamespace(id=identity,system_role='user') if identity else None
                request.state.auth=AuthContext(user,['threads:read','threads:write','agents:read'] if identity!='denied' else [])
                token=set_current_user(user)
                try:return await call_next(request)
                finally:reset_current_user(token)
            store=SimpleNamespace(check_access=AsyncMock(side_effect=lambda thread,user,require_existing=False:thread=='guided' and user=='alice'))
            paths=SimpleNamespace(sandbox_user_data_dir=lambda thread,user_id:root/user_id/thread)
            with patch('app.gateway.deps.get_thread_store',return_value=store),patch('righaven.recipe_routes.get_paths',return_value=paths),patch('righaven.capability_policy.native_policy',return_value={'skill_names':['skill-data-pipeline']}),patch.object(state,'STATE',root/'state'),TestClient(app) as client:
                url='/api/threads/guided/harness-journey';headers={'X-Test-User':'alice'}
                self.assertEqual(client.get(url).status_code,401)
                self.assertEqual(client.get(url,headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.get(url,headers={'X-Test-User':'denied'}).status_code,403)
                body={'recipe_id':'data-pipeline','answers':{'goal':'Document the supplied schema'},'expected_revision':0}
                self.assertEqual(client.put(url,json={**body,'recipe_id':'unknown-workflow'},headers=headers).status_code,404)
                response=client.put(url,json=body,headers=headers);self.assertEqual(response.status_code,200,response.text)
                saved=response.json()['journey'];self.assertTrue(saved['connections_optional'])
                self.assertEqual(client.get(url,headers=headers).json()['journey']['revision'],saved['revision'])
                self.assertEqual(client.put(url,json=body,headers=headers).status_code,200)
                conflict={**body,'answers':{'goal':'A competing edit'}}
                self.assertEqual(client.put(url,json=conflict,headers=headers).status_code,409)
                work=root/'alice/guided';projects.create_plan(work,'Read documentation',[{'id':'read','agent':'workspace','goal':'Catalog','depends_on':[]}])
                artifact=work/'catalog.md';artifact.write_text('Documented model')
                pending=journeys.record(work,'understand',[str(artifact)],['read'],'Actual catalog for owner review',saved['revision'])
                decision={'stage_id':'understand','approve':True,'expected_revision':pending['revision']}
                self.assertEqual(client.post(url+'/decision',json=decision,headers={'X-Test-User':'bob'}).status_code,404)
                result=client.post(url+'/decision',json=decision,headers=headers);self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['journey']['current'],'design')
                skip={'stage_id':'design','action':'skip','expected_revision':result.json()['journey']['revision'],'note':'Not needed'}
                skipped=client.post(url+'/decision',json=skip,headers=headers);self.assertEqual(skipped.status_code,200,skipped.text)
                self.assertEqual(skipped.json()['journey']['stages'][1]['status'],'skipped')
                self.assertEqual(client.post(url+'/decision',json={**skip,'action':'erase'},headers=headers).status_code,422)

    def test_user_recipe_editor_crud_sharing_and_guided_start(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven import state
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=FastAPI();app.include_router(recipe_router);app.include_router(journey_router)
            @app.middleware('http')
            async def auth(request,call_next):
                identity=request.headers.get('X-Test-User');user=SimpleNamespace(id=identity,system_role='user') if identity else None
                request.state.auth=AuthContext(user,['threads:read','threads:write','agents:read'])
                token=set_current_user(user)
                try:return await call_next(request)
                finally:reset_current_user(token)
            store=SimpleNamespace(check_access=AsyncMock(return_value=True))
            paths=SimpleNamespace(sandbox_user_data_dir=lambda thread,user_id:root/user_id/thread)
            admin=AsyncMock(side_effect=lambda request:request.headers.get('X-Test-User')=='admin')
            policy={'skill_names':['skill-harness','skill-duckdb']}
            with patch('app.gateway.deps.get_thread_store',return_value=store),patch('righaven.recipe_routes.get_paths',return_value=paths),\
                 patch('righaven.capability_policy.native_policy',return_value=policy),patch('righaven.recipe_routes.is_admin_user',admin),\
                 patch('righaven.environments.skill_inventory',return_value=[SimpleNamespace(name='skill-duckdb',description='DuckDB')]),\
                 patch.object(state,'STATE',root/'state'),TestClient(app) as client:
                alice={'X-Test-User':'alice'};bob={'X-Test-User':'bob'}
                draft={'title':'Dashboard demo','summary':'Dashboard con dati di esempio','when':'Per una demo veloce',
                       'attach_required':['Elenco indicatori'],'outputs':['Dashboard HTML'],
                       'phases':[{'title':'Indicatori','detail':'Misure concordate','checkpoint':True},{'title':'Dashboard','detail':'Report','checkpoint':False}],
                       'skills':['skill-duckdb'],'environment':'dati'}
                self.assertEqual(client.post('/api/harness/recipes',json={**draft,'skills':['skill-data-pipeline']},headers=alice).status_code,400)
                created=client.post('/api/harness/recipes',json=draft,headers=alice);self.assertEqual(created.status_code,200,created.text)
                recipe=created.json()['recipe'];self.assertTrue(recipe['mine'])
                self.assertNotIn(recipe['id'],[r['id'] for r in client.get('/api/harness/recipes',headers=bob).json()['recipes']])
                self.assertEqual(client.put('/api/harness/recipes/'+recipe['id'],json={**draft,'expected_revision':recipe['revision']},headers=bob).status_code,409)
                edited=client.put('/api/harness/recipes/'+recipe['id'],json={**draft,'title':'Demo vendite','expected_revision':recipe['revision']},headers=alice)
                self.assertEqual(edited.json()['recipe']['title'],'Demo vendite')
                self.assertEqual(client.put('/api/harness/recipes/'+recipe['id']+'/sharing',json={'shared':True},headers=alice).status_code,403)
                self.assertEqual(client.put('/api/harness/recipes/'+recipe['id']+'/sharing',json={'shared':True},headers={'X-Test-User':'admin'}).status_code,200)
                self.assertIn(recipe['id'],[r['id'] for r in client.get('/api/harness/recipes',headers=bob).json()['recipes']])
                options=client.get('/api/harness/recipes/editor/options',headers=alice).json()
                self.assertIn('dati',[e['id'] for e in options['environments']])
                copy=client.get('/api/harness/recipes/data-pipeline/draft',headers=alice).json()['draft'];self.assertEqual(copy['based_on'],'data-pipeline')
                started=client.put('/api/threads/demo/harness-journey',json={'recipe_id':recipe['id'],'answers':{'goal':'Demo'}},headers=bob)
                self.assertEqual(started.status_code,200,started.text);self.assertEqual(started.json()['journey']['stages'][1]['gate'],False)
                self.assertEqual(client.delete('/api/harness/recipes/'+recipe['id'],headers=bob).status_code,403)
                self.assertEqual(client.delete('/api/harness/recipes/'+recipe['id'],headers=alice).status_code,200)
