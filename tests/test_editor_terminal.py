"""Editor terminals reuse the native terminal service with an owned writable project."""
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock,patch
try:
    from app.gateway.authz import AuthContext
    from righaven_core.runtime.user_context import set_current_user,reset_current_user
    from righaven.editor_proxy import router
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    router=None


@unittest.skipIf(router is None,'Requires native Gateway SDK')
class EditorTerminal(unittest.TestCase):
    def test_owned_text_editor_terminal_has_same_files_and_lifecycle(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven import editor_documents as documents
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);project=root/'alice/conversation';(project/'outputs').mkdir(parents=True);(project/'outputs/script.py').write_text('print(42)')
            app=FastAPI();app.include_router(router)
            @app.middleware('http')
            async def auth(request,call_next):
                user=SimpleNamespace(id=request.headers.get('X-Test-User','alice'),system_role='user')
                request.state.auth=AuthContext(user,['threads:read','threads:write','agents:write'])
                token=set_current_user(user)
                try:return await call_next(request)
                finally:reset_current_user(token)
            paths=SimpleNamespace(sandbox_user_data_dir=lambda thread,user_id:root/user_id/thread)
            store=SimpleNamespace(check_access=AsyncMock(side_effect=lambda thread,user,require_existing=False:thread=='conversation' and user=='alice'))
            doc=documents.start(project,'/mnt/user-data/outputs/script.py','text',[],direct=True)
            profile={'name':'python-env','tools':['jupyter'],'skills':['skill-jupyter']}
            record={'id':'e'*64,'image_id':'sha256:fixture','tools':['jupyter'],'status':'ready'}
            profile['runtime']=record
            with patch('app.gateway.deps.get_thread_store',return_value=store),patch('righaven.collaboration_routes.get_paths',return_value=paths),patch('righaven.capability_policy.native_policy',return_value={'allowed':['jupyter']}),patch('righaven.environment_routes.native_agent',new=AsyncMock(return_value=SimpleNamespace(name='python-env'))),patch('righaven.environments.profile',return_value=profile),patch('righaven.environment_routes.checked_summary',new=AsyncMock(return_value=profile)),patch('righaven.tool_versions.software_selections',return_value={}),patch('righaven.tool_versions.resolved',return_value={}),patch('righaven.environment_runtime.ensure',return_value=record),patch('righaven.environment_runtime.claim_environment',side_effect=lambda record,claim:record),patch('righaven.environment_runtime.release_claim') as release,patch('righaven.environment_terminal.start',return_value={'id':'native-terminal'}) as start,TestClient(app) as client:
                url='/api/threads/conversation/editors/'+doc['id']+'/terminal'
                body={'client_id':'a'*32}
                self.assertEqual(client.post(url+'?environment=python-env',json=body,headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.post(url+'?environment=python-env',json=body,headers={'Origin':'https://foreign.example'}).status_code,403)
                self.assertEqual(client.post(url,json=body).status_code,409)
                response=client.post(url+'?environment=python-env',json=body)
                self.assertEqual(response.status_code,201,response.text)
                args=start.call_args.args
                self.assertEqual(args[:2],('alice','python-env'))
                selected=args[2]
                self.assertEqual(selected['_thread_id'],'conversation')
                self.assertEqual(selected['_editor_session'],doc['id'])
                self.assertEqual(selected['_terminal_workdir'],'/workspace/output')
                self.assertIn((project/'outputs','/workspace/output',False),selected['_terminal_mounts'])
                self.assertEqual(len(selected['_terminal_mounts']),7)
                self.assertIn((project/'uploads','/mnt/user-data/uploads',False),selected['_terminal_mounts'])
                self.assertEqual(selected['_terminal_workspace_root'],'/mnt/user-data')
                self.assertTrue(all(not path.name.startswith('.') and not readonly for path,_,readonly in selected['_terminal_mounts']))
                release.assert_called()
                # Core-only environments have no saved image record. Preserve
                # the same base-image fallback used by ordinary terminals.
                profile['runtime']={'id':'b'*64,'status':'ready','tools':[],'core':True}
                response=client.post(url+'?environment=python-env',json=body)
                self.assertEqual(response.status_code,201,response.text)
                self.assertIsNone(start.call_args.args[2]['_terminal_record'])
