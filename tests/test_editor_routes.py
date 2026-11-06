"""Native ownership protects drafts, assets, publication and service launch."""
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
class EditorRoutes(unittest.TestCase):
    def test_owner_permissions_origin_and_conflicting_draft_writes(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from righaven import state
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'alice/conversation/outputs').mkdir(parents=True);(root/'alice/conversation/outputs/source.md').write_text('Original')
            app=FastAPI();app.include_router(router)
            @app.middleware('http')
            async def auth(request,call_next):
                identity=request.headers.get('X-Test-User');user=SimpleNamespace(id=identity,system_role='user') if identity else None
                request.state.auth=AuthContext(user,['threads:read','threads:write','agents:read','agents:write'] if identity!='denied' else [])
                token=set_current_user(user)
                try:return await call_next(request)
                finally:reset_current_user(token)
            paths=SimpleNamespace(sandbox_user_data_dir=lambda thread,user_id:root/user_id/thread)
            store=SimpleNamespace(check_access=AsyncMock(side_effect=lambda thread,user,require_existing=False:thread=='conversation' and user=='alice'))
            with patch('app.gateway.deps.get_thread_store',return_value=store),patch('righaven.collaboration_routes.get_paths',return_value=paths),patch('righaven.capability_policy.native_policy',return_value={'allowed':[]}),patch.object(state,'STATE',root/'state'),TestClient(app) as client:
                base='/api/threads/conversation/editors';owner={'X-Test-User':'alice'}
                for identity,expected in [(None,401),('bob',404),('denied',403)]:self.assertEqual(client.get(base,headers={'X-Test-User':identity} if identity else {}).status_code,expected)
                files_url='/api/threads/conversation/project-files'
                self.assertEqual(client.get(files_url,headers=owner).status_code,200)
                self.assertEqual(client.get(files_url+'?path=outputs',headers=owner).json()['entries'][0]['name'],'source.md')
                self.assertEqual(client.get(files_url,headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.get(files_url+'?path=../bob',headers=owner).status_code,409)
                payload={'path':'/mnt/user-data/outputs/source.md','editor':'text'}
                self.assertEqual(client.post(base,json=payload,headers={**owner,'Origin':'https://foreign.example'}).status_code,403)
                response=client.post(base,json=payload,headers=owner);self.assertEqual(response.status_code,200,response.text);url=base+'/'+response.json()['id']
                for endpoint in [url,url+'/files/source.md',url+'/package',url+'/service/proxy/api/contents']:self.assertEqual(client.get(endpoint,headers={'X-Test-User':'bob'}).status_code,404)
                presence={'client':'12345678-1234-1234-1234-123456789012','active':True}
                self.assertEqual(client.post(url+'/presence',json=presence,headers={'X-Test-User':'bob'}).status_code,404)
                self.assertEqual(client.post(url+'/presence',json=presence,headers={**owner,'Origin':'https://foreign.example'}).status_code,403)
                self.assertEqual(client.post(url+'/presence',json=presence,headers=owner).status_code,200)
                from righaven import editor_presence
                self.assertEqual(len(editor_presence.activity('alice')),1)
                self.assertEqual(client.post(url+'/presence',json={**presence,'active':False},headers=owner).status_code,200)
                self.assertEqual(editor_presence.activity('alice'),[])
                response=client.put(url+'/files/source.md?expected_revision=0&entry=true',content=b'Edited',headers=owner);self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(client.put(url+'/files/source.md?expected_revision=0',content=b'Conflict',headers=owner).status_code,409)
                choices=client.get(base+'?session='+url.rsplit('/',1)[1],headers=owner)
                self.assertEqual(choices.status_code,200);self.assertIn('available_editors',choices.json())
                self.assertEqual(client.post(url+'/open-with',json={'editor':'text'},headers={'X-Test-User':'bob','Origin':'http://testserver'}).status_code,404)
                self.assertEqual(client.post(url+'/open-with',json={'editor':'text'},headers={**owner,'Origin':'https://foreign.example'}).status_code,403)
                copied=client.post(url+'/open-with',json={'editor':'text'},headers=owner)
                self.assertEqual(copied.status_code,200,copied.text);self.assertNotEqual(copied.json()['id'],url.rsplit('/',1)[1])
                self.assertEqual(client.get(base+'/'+copied.json()['id']+'/files/source.md',headers=owner).content,b'Edited')
                response=client.post(url+'/publish',json={'expected_revision':1},headers=owner);self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['exports_regenerated'])
                response=client.get(url+'/files/source.md',headers=owner);self.assertEqual(response.content,b'Edited');self.assertEqual(response.headers['content-type'],'application/octet-stream')
                self.assertEqual(client.post(url+'/service',headers=owner).status_code,409)
                from starlette.websockets import WebSocketDisconnect
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect(url+'/service/proxy/websockify',headers={'Origin':'https://foreign.example','Cookie':'rh_editor=wrong'}):pass

                # A valid scoped WebSocket reaches only our own service. Account
                # cookies and account authorization are not forwarded upstream.
                import asyncio,threading,httpx
                from righaven import editor_runtime
                from websockets.asyncio.server import serve
                ready=threading.Event();stop=threading.Event();port=[];received=[]
                async def echo(connection):
                    received.append(dict(connection.request.headers))
                    await connection.send(await connection.recv())
                def backend():
                    async def run():
                        async with serve(echo,'127.0.0.1',0) as server:
                            port.append(server.sockets[0].getsockname()[1]);ready.set()
                            await asyncio.to_thread(stop.wait)
                    asyncio.run(run())
                worker=threading.Thread(target=backend,daemon=True);worker.start();self.assertTrue(ready.wait(5))
                service=SimpleNamespace(workspace=root/'alice/conversation',sid=url.rsplit('/',1)[1],user='alice',thread='conversation',state='ready',closed=False,csp_nonce='nonce-fixture',cookie='scoped-editor-fixture',token='backend-fixture',document={'editor':'jupyter'},proxy=url+'/service/proxy/',target='http://127.0.0.1:'+str(port[0]),cancel=threading.Event())
                actual_client=httpx.AsyncClient;requests=[]
                def transport(request):
                    requests.append(request)
                    if request.url.path.endswith('.html') or '/notebooks/' in request.url.path:return httpx.Response(200,stream=httpx.ByteStream(b'<html><head><script id="jupyter-config-data" type="application/json">{"token":"private-notebook-token"}</script><script>window.fixture=true;</script></head></html>'),headers={'Content-Type':'text/html'})
                    return httpx.Response(200,stream=httpx.ByteStream(b'{"ok":true}'),headers={'Content-Type':'application/json'})
                def private_client(**kwargs):return actual_client(**kwargs,transport=httpx.MockTransport(transport))
                try:
                    with patch.dict(editor_runtime.SESSIONS,{'fixture':service},clear=True),patch('httpx.AsyncClient',side_effect=private_client):
                        client.cookies.set('access_token','account-cookie-fixture')
                        response=client.get(url+'/service/proxy/api/contents',headers={**owner,'Authorization':'Bearer account-fixture'})
                        self.assertEqual(response.status_code,200,response.text)
                        self.assertEqual(requests[0].headers['Authorization'],'token backend-fixture')
                        self.assertNotIn('cookie',requests[0].headers)
                        self.assertTrue(str(requests[0].url).startswith(service.target+service.proxy))
                        self.assertIn("script-src 'nonce-nonce-fixture'",response.headers['content-security-policy'])
                        untrusted=client.get(url+'/service/proxy/files/untrusted.html',headers=owner)
                        self.assertEqual(untrusted.headers['content-type'],'application/octet-stream');self.assertEqual(untrusted.headers['content-disposition'],'attachment')
                        trusted=client.get(url+'/service/proxy/notebooks/source.ipynb',headers=owner)
                        self.assertIn('<script nonce="nonce-fixture">',trusted.text);self.assertIn('X-CSRF-Token',trusted.text)
                        self.assertNotIn("'unsafe-eval'",trusted.headers['content-security-policy'])
                        self.assertNotIn('private-notebook-token',trusted.text)
                        self.assertIn("headers.delete('Authorization')",trusted.text)
                        count=len(requests)
                        for hook in ('custom/custom.js','custom/custom-preload.js'):
                            hook_response=client.get(url+'/service/proxy/'+hook,headers=owner)
                            self.assertEqual(hook_response.text,'define(function(){return {};});');self.assertIn('application/javascript',hook_response.headers['content-type'])
                        shim=client.get(url+'/service/proxy/static/components/es6-promise/promise.min.js',headers=owner)
                        self.assertIn('Promise:globalThis.Promise',shim.text);self.assertNotIn('eval(',shim.text)
                        self.assertEqual(len(requests),count,'Never read user-provided extension hooks or the eval-based legacy polyfill')
                        self.assertIn('HttpOnly',response.headers['set-cookie']);self.assertIn('SameSite=strict',response.headers['set-cookie'])
                        self.assertEqual(client.post(url+'/publish',json={'expected_revision':1},headers=owner).status_code,409)
                        with client.websocket_connect(url+'/service/proxy/api/kernels/fixture/channels',headers={'Origin':'http://testserver'}) as socket:
                            socket.send_text('round-trip');self.assertEqual(socket.receive_text(),'round-trip')
                        self.assertEqual(received[0]['authorization'],'token backend-fixture');self.assertNotIn('cookie',received[0])
                        with self.assertRaises(WebSocketDisconnect):
                            with client.websocket_connect(url.replace('/conversation/','/another-conversation/')+'/service/proxy/api/kernels/fixture/channels',headers={'Origin':'http://testserver'}):pass
                finally:stop.set();worker.join(5)
