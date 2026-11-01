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
    from righaven.recipe_routes import journey_router
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
