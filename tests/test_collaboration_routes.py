"""Native ownership, pre-plan consent and owner-only method decisions."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
try:
    from app.gateway.authz import AuthContext
    from righaven_core.runtime.user_context import set_current_user, reset_current_user
    from righaven.collaboration_routes import router as method_router
    from righaven.connection_routes import router as connection_router
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1': raise
    method_router=None


@unittest.skipIf(method_router is None,'Requires the native Gateway')
class CollaborationRoutes(unittest.TestCase):
    def test_preplan_connections_and_method_choices_are_owner_scoped(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from cryptography.fernet import Fernet
        from righaven import collaboration,connections,projects
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);app=FastAPI();app.include_router(method_router);app.include_router(connection_router)
            @app.middleware('http')
            async def auth(request,call_next):
                identity=request.headers.get('X-Test-User');user=SimpleNamespace(id=identity,system_role='user') if identity else None
                request.state.auth=AuthContext(user,['threads:read','threads:write','agents:read'] if identity!='denied' else [])
                token=set_current_user(user)
                try:return await call_next(request)
                finally:reset_current_user(token)
            store=SimpleNamespace(check_access=AsyncMock(side_effect=lambda thread,user,require_existing=False:thread=='conversation' and user=='alice'))
            paths=SimpleNamespace(sandbox_user_data_dir=lambda thread,user_id:root/user_id/thread)
            running=AsyncMock(return_value=False)
            with patch('app.gateway.deps.get_thread_store',return_value=store), \
                 patch('righaven.collaboration_routes.get_paths',return_value=paths), \
                 patch('righaven.connection_routes.get_paths',return_value=paths), \
                 patch('righaven.progress_routes.production_running',new=running), \
                 patch('righaven.capability_policy.native_policy',return_value={'allowed':['typst'],'skill_names':['skill-typst']}), \
                 patch.object(connections,'folder',side_effect=lambda user:root/user/'credentials'), \
                 patch.dict(os.environ,{'RIGHAVEN_CREDENTIALS_KEY':Fernet.generate_key().decode()}), TestClient(app) as client:
                (root/'alice'/'credentials').mkdir(parents=True)
                connections.save('alice',{'id':'source','kind':'postgres','name':'Source','host':'database.example.com','database':'db','username':'reader','password':'private-fixture','read_only':True})
                url='/api/threads/conversation';headers={'X-Test-User':'alice'}
                self.assertEqual(client.get(url+'/harness-method').status_code,401)
                self.assertEqual(client.get(url+'/harness-method',headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.get(url+'/harness-method',headers={'X-Test-User':'denied'}).status_code,403)
                # Native thread exists, no production project or recipe exists.
                result=client.put(url+'/harness-connections',json={'ids':['source']},headers=headers)
                self.assertEqual(result.status_code,200,result.text)
                self.assertNotIn('private-fixture',result.text)
                workspace=root/'alice'/'conversation'
                self.assertIsNone(projects.read_project(workspace))
                self.assertEqual(client.get(url+'/harness-connections',headers=headers).json()['assigned'][0]['id'],'source')
                self.assertEqual(client.put(url+'/harness-connections',json={'ids':['source']},headers={'X-Test-User':'bob'}).status_code,404)
                projects.create_plan(workspace,'Produce a document',[],strategy={'method':'Typeset','reason':'Editable and verifiable',
                    'state':'needs_user','stop_reason':'user_choice','user_action':'Choose an approach', 'alternatives':[]})
                sig=collaboration.view(workspace)['signature'];choice={'signature':sig,'choice':0,'note':'Keep the sources'}
                self.assertEqual(client.post(url+'/harness-method/choice',json=choice,headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.post(url+'/harness-method/choice',json=choice,headers={**headers,'Origin':'https://foreign.example'}).status_code,403)
                running.return_value=True
                self.assertEqual(client.post(url+'/harness-method/choice',json=choice,headers=headers).status_code,409)
                running.return_value=False
                saved=client.post(url+'/harness-method/choice',json=choice,headers=headers)
                self.assertEqual(saved.status_code,200,saved.text)
                self.assertEqual(saved.json()['decision']['note'],'Keep the sources')
                self.assertEqual(client.post(url+'/harness-method/choice',json={**choice,'signature':'0'*64},headers=headers).status_code,409)
                self.assertEqual(client.post(url+'/harness-method/choice',json={**choice,'approve':True},headers=headers).status_code,422)
                self.assertEqual(client.get(url+'/harness-method/recipe',headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.get(url+'/harness-method/recipe',headers=headers).status_code,409)
                self.assertEqual([c['id'] for c in projects.read_project(workspace)['connections']],['source'])
                source=workspace/'outputs'/'source.md';source.parent.mkdir();source.write_text('Original')
                from righaven.source_packages import digest
                edit={'path':'/mnt/user-data/outputs/source.md','expected_sha256':digest(source),'content':'User edit'}
                self.assertEqual(client.post(url+'/harness-source-edits',json=edit,headers={'X-Test-User':'bob'}).status_code,404)
                running.return_value=True
                self.assertEqual(client.post(url+'/harness-source-edits',json=edit,headers=headers).status_code,409)
                running.return_value=False
                edited=client.post(url+'/harness-source-edits',json=edit,headers=headers)
                self.assertEqual(edited.status_code,200,edited.text)
                self.assertFalse(edited.json()['exports_regenerated'])
                self.assertEqual(source.read_text(),'Original')

                current=client.get(url+'/harness-objective',headers=headers)
                self.assertEqual(current.status_code,200,current.text)
                change={'signature':current.json()['signature'],'goal':'Use this result for a new customer portal'}
                self.assertEqual(client.post(url+'/harness-objective',json=change,headers={'X-Test-User':'bob'}).status_code,404)
                running.return_value=True
                self.assertEqual(client.post(url+'/harness-objective',json=change,headers=headers).status_code,409)
                running.return_value=False
                moved=client.post(url+'/harness-objective',json=change,headers=headers)
                self.assertEqual(moved.status_code,200,moved.text)
                self.assertTrue(moved.json()['changed']);self.assertTrue(source.exists())
                self.assertEqual(client.post(url+'/harness-objective',json=change,headers=headers).json()['changed'],False)
                self.assertIsNone(projects.read_project(workspace)['strategy'])
