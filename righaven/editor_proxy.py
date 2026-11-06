"""Authenticated HTTP/WebSocket access to our own isolated editor containers."""
import asyncio
from pathlib import Path
import secrets
import re
import time
from urllib.parse import urlencode,urlsplit
from fastapi import Request,HTTPException,WebSocket
from fastapi.responses import HTMLResponse,StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from app.gateway.authz import require_permission
from righaven_core.utils.thread_id import ThreadId
from righaven_core.runtime.user_context import get_effective_user_id
from .editor_routes import router,allowed,failure
from .collaboration_routes import workspace
from .router import same_origin
from . import editor_runtime as runtimes,editor_documents as documents


async def authorized(thread_id,sid):
    policy=await allowed();user=get_effective_user_id();root=workspace(thread_id)
    def check():
        from .project_store import locked
        with locked(root) as folder:documents.record(folder,sid,policy)
    try:await run_in_threadpool(check)
    except ValueError as error:
        service=runtimes.find(root,sid,user)
        if service:service.cancel.set()
        raise failure(error) from error
    return root,user,policy


@router.post('/api/threads/{thread_id}/editors/{sid}/service')
@require_permission('threads','write',owner_check=True,require_existing=True)
@require_permission('agents','write')
async def start_service(thread_id:ThreadId,sid:str,request:Request):
    same_origin(request);root,user,policy=await authorized(thread_id,sid)
    try:
        from .editor_profiles import ensure
        await ensure(root,sid,user,request,policy)
        return (await run_in_threadpool(runtimes.start,root,sid,user,thread_id,policy)).public()
    except ValueError as error:raise failure(error) from error


from .environment_routes import TerminalOpen


@router.post('/api/threads/{thread_id}/editors/{sid}/terminal',status_code=201)
@require_permission('threads','write',owner_check=True,require_existing=True)
@require_permission('agents','write')
async def project_terminal(thread_id:ThreadId,sid:str,request:Request,value:TerminalOpen,environment:str=''):
    """Use the ordinary terminal lifecycle with this editor's writable folder."""
    same_origin(request);root,user,policy=await authorized(thread_id,sid)
    from . import editor_profiles,editor_catalog,editor_versions,environment_terminal,environments,environment_runtime
    from .environment_routes import native_agent,checked_summary
    from .capability_policy import native_policy
    from .project_store import locked
    claim='editor-terminal-'+sid+'-'+(value.client_id or 'window')
    try:
        document=await run_in_threadpool(documents.metadata,root,sid,policy)
        definition=editor_catalog.editor(document['editor'],policy)
        if definition['tool']:
            name=await editor_profiles.ensure(root,sid,user,request,policy,terminal=True)
            document=await run_in_threadpool(documents.metadata,root,sid,policy)
            software=await run_in_threadpool(editor_versions.software,document,definition['tool'],claim,None,user=user)
        else:
            if not environment:raise ValueError('Select an environment for this project terminal')
            name=environment
        agent=await native_agent(request,name)
        profile=await run_in_threadpool(environments.profile,user,agent)
        scoped=await run_in_threadpool(native_policy,user,name)
        if not definition['tool']:
            profile=await checked_summary(user,agent)
            if profile['runtime']['status']!='ready':raise ValueError('Prepare the environment before opening the project terminal')
            software=await run_in_threadpool(environment_runtime.claim_environment,profile['runtime'],claim)
        def directory():
            with locked(root) as folder:
                saved,_=documents.record(folder,sid,policy)
                return documents.file_root(saved)
        mounts=[(await run_in_threadpool(directory),'/workspace/output',False)]
        if document.get('mode')=='project':
            for public in ('uploads','outputs','workspace'):
                path=documents.confined(Path(root),Path(root)/public);path.mkdir(parents=True,exist_ok=True)
                mounts.extend([(path,'/workspace/chat/'+public,False),(path,'/mnt/user-data/'+public,False)])
        profile.update(runtime=software,_terminal_record=software if software.get('image_id') else None,_terminal_mounts=mounts,
                       _terminal_workdir='/workspace/output',_terminal_workspace_root='/mnt/user-data' if document.get('mode')=='project' else '/workspace/output',_thread_id=str(thread_id),_editor_session=sid)
        return await run_in_threadpool(environment_terminal.start,user,name,profile,scoped,client_id=value.client_id)
    except (ValueError,OSError) as error:raise failure(error) from error
    finally:await run_in_threadpool(environment_runtime.release_claim,claim)


@router.get('/api/threads/{thread_id}/editors/{sid}/service')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def current_service(thread_id:ThreadId,sid:str,request:Request):
    root,user,_=await authorized(thread_id,sid)
    service=next((s for s in reversed(list(runtimes.SESSIONS.values())) if s.workspace==Path(root) and s.sid==sid and s.user==user),None)
    return service.public() if service else {'state':'stopped','message':'Editor not running'}


@router.delete('/api/threads/{thread_id}/editors/{sid}/service')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def stop_service(thread_id:ThreadId,sid:str,request:Request):
    same_origin(request);service=runtimes.find(workspace(thread_id),sid,get_effective_user_id())
    if service:service.state='stopping';service.message='Closing editor; retaining saved draft files';service.cancel.set()
    return {'state':'stopping' if service else 'stopped'}


# Classic Notebook requires these extension hooks even without extensions.
# Serve fixed no-op modules; never execute user-provided custom JavaScript.
CUSTOM_HOOKS=('custom/custom.js','custom/custom-preload.js')
NOTEBOOK_SHIMS={hook:'define(function(){return {};});' for hook in CUSTOM_HOOKS}
# Debian's legacy Promise polyfill uses an eval-based development bundle.
# Every supported browser already provides native Promise; preserve its API.
NOTEBOOK_SHIMS['static/components/es6-promise/promise.min.js']="globalThis.ES6Promise={Promise:globalThis.Promise,polyfill:function(){}};if(typeof define==='function'&&define.amd)define(function(){return globalThis.ES6Promise;});"

CSRF_BRIDGE="""<script>(()=>{const prefix=PREFIX;addEventListener('message',event=>{if(event.source===parent&&event.origin===location.origin&&event.data?.type==='rh-lab-terminal'&&window.jupyterapp)void jupyterapp.commands.execute('terminal:create-new');});const token=()=>decodeURIComponent(document.cookie.split('; ').find(v=>v.startsWith('csrf_token='))?.slice(11)||'');const write=m=>!['GET','HEAD','OPTIONS'].includes((m||'GET').toUpperCase());const own=u=>{const v=new URL(u,location.href);return v.origin===location.origin&&v.pathname.startsWith(prefix);};const open=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(method,url,...args){this.rhOwn=own(url);this.rhWrite=write(method)&&this.rhOwn;return open.call(this,method,url,...args);};const setHeader=XMLHttpRequest.prototype.setRequestHeader;XMLHttpRequest.prototype.setRequestHeader=function(name,value){if(this.rhOwn&&name.toLowerCase()==='authorization')return;return setHeader.call(this,name,value);};const send=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.send=function(...args){if(this.rhWrite)this.setRequestHeader('X-CSRF-Token',token());return send.apply(this,args);};const fetch=window.fetch;window.fetch=function(input,init={}){const url=typeof input==='string'?input:input.url,method=init.method||(typeof input==='object'?input.method:'GET');if(own(url)){const headers=new Headers(init.headers||(typeof input==='object'?input.headers:undefined));headers.delete('Authorization');if(write(method))headers.set('X-CSRF-Token',token());init={...init,headers,credentials:'same-origin'};}return fetch.call(this,input,init);};})();</script>"""


@router.api_route('/api/threads/{thread_id}/editors/{sid}/service/proxy/{path:path}',methods=['GET','POST','PUT','PATCH','DELETE','HEAD'])
@require_permission('threads','write',owner_check=True,require_existing=True)
async def proxy_http(thread_id:ThreadId,sid:str,path:str,request:Request):
    import httpx
    root,user,_=await authorized(thread_id,sid)
    if request.method not in ('GET','HEAD'):same_origin(request)
    service=runtimes.find(root,sid,user)
    if not service or service.state!='ready':raise HTTPException(409,'Interactive editor is not ready')
    service.last_seen=time.monotonic()
    if path.startswith('/') or '..' in path.split('/'):raise HTTPException(400,'Invalid editor path')
    # Stream large notebook uploads to disk instead of buffering/capping all
    # requests at 64 MiB. Account authorization still runs before reading a body.
    import tempfile
    body_file=tempfile.TemporaryFile() if request.method not in ('GET','HEAD') else None
    if body_file is not None:
        from starlette.requests import ClientDisconnect
        try:
            async for chunk in request.stream():await run_in_threadpool(body_file.write,chunk)
            body_file.seek(0)
        except ClientDisconnect:
            body_file.close()
            from fastapi.responses import Response
            return Response(status_code=499)
    async def body_chunks():
        if body_file is not None:
            try:
                while True:
                    chunk=await run_in_threadpool(body_file.read,65536)
                    if not chunk:break
                    yield chunk
            finally:body_file.close()
    if service.document['editor']=='jupyter' and path in NOTEBOOK_SHIMS:
        from fastapi.responses import Response
        return Response(NOTEBOOK_SHIMS[path],media_type='application/javascript',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
    backend_path=service.proxy+path if service.document['editor']=='jupyter' else '/'+path
    headers={k:v for k,v in request.headers.items() if k.lower() in ('content-type','accept','if-none-match','range')}
    headers.update(Authorization='token '+service.token,**{'Accept-Encoding':'identity'})
    client=httpx.AsyncClient(timeout=120,trust_env=False,follow_redirects=False)
    try:upstream=await client.send(client.build_request(request.method,service.target+backend_path,params=list(request.query_params.multi_items()),headers=headers,content=body_chunks() if body_file is not None else None),stream=True)
    except httpx.HTTPError as error:
        if body_file is not None:body_file.close()
        await client.aclose();raise HTTPException(502,'Editor connection failed') from error
    if body_file is not None:body_file.close()
    content_type=upstream.headers.get('content-type','')
    notebook=service.document['editor']=='jupyter'
    trusted_page=notebook and (not path or path.startswith(('tree','notebooks/','edit/','terminals/','login','lab','workspaces')))
    untrusted_content=notebook and (('text/html' in content_type and not trusted_page) or (('javascript' in content_type or 'ecmascript' in content_type) and not path.startswith(('static/','lab/extensions/'))))
    if untrusted_content:
        download_headers={k:v for k,v in upstream.headers.items() if k.lower() in ('content-length','content-range','accept-ranges','content-encoding')}
        download_headers.update({'Content-Type':'application/octet-stream','Content-Disposition':upstream.headers.get('content-disposition','attachment'),'X-Content-Type-Options':'nosniff'})
        async def close_download():await upstream.aclose();await client.aclose()
        response=StreamingResponse(upstream.aiter_raw(),status_code=upstream.status_code,headers=download_headers,background=BackgroundTask(close_download))
    elif 'text/html' in content_type:
        body=(await upstream.aread()).decode('utf-8');await upstream.aclose();await client.aclose()
        import json
        if notebook:
            # Jupyter's internal token authenticates Gateway -> server only.
            # Sending it from Lab would override the browser's account cookie
            # at the Gateway's strict PAT authentication boundary.
            def public_config(match):
                data=json.loads(match.group(2));data['token']=''
                return match.group(1)+json.dumps(data).replace('<','\\u003c')+match.group(3)
            body=re.sub(r'(<script\b(?=[^>]*\bid=[\"\']jupyter-config-data[\"\'])[^>]*>)(.*?)(</script>)',public_config,body,flags=re.DOTALL|re.IGNORECASE)
        body=body.replace('<head>','<head>'+CSRF_BRIDGE.replace('PREFIX',json.dumps(service.proxy)),1)
        if notebook:
            body=re.sub(r'<script(?=[\s>])', '<script nonce="'+service.csp_nonce+'"',body,flags=re.IGNORECASE)
        response=HTMLResponse(body,status_code=upstream.status_code)
    else:
        response_headers={k:v for k,v in upstream.headers.items() if k.lower() in ('content-type','content-length','content-range','accept-ranges','etag','last-modified','content-encoding','content-disposition')}
        if 'location' in upstream.headers:
            location=upstream.headers['location']
            if location.startswith(service.target):location=location[len(service.target):]
            response_headers['location']=location if location.startswith('/') and not location.startswith('//') else service.proxy
        async def cleanup():await upstream.aclose();await client.aclose()
        response=StreamingResponse(upstream.aiter_raw(),status_code=upstream.status_code,headers=response_headers,background=BackgroundTask(cleanup))
    # Only this session's scoped handshake cookie enters WebSockets. Neither
    # account cookies nor account/API Authorization headers reach the service.
    response.set_cookie('rh_editor',service.cookie,httponly=True,samesite='strict',path=service.proxy,secure=request.url.scheme=='https',max_age=7200)
    response.headers['Cache-Control']='no-store'
    if notebook:
        static=request.headers.get('host','')+service.proxy+'static/'
        hooks=' '.join(request.headers.get('host','')+service.proxy+hook for hook in CUSTOM_HOOKS)
        evaluation="'unsafe-eval' 'wasm-unsafe-eval' " if path.startswith('lab') else ''
        response.headers['Content-Security-Policy']=f"default-src 'none'; script-src 'nonce-{service.csp_nonce}' {evaluation}{static} {request.headers.get('host','')+service.proxy+'lab/extensions/'} {hooks}; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' ws://{request.headers.get('host','')}{service.proxy} wss://{request.headers.get('host','')}{service.proxy}; worker-src 'self' blob:; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"
    return response


@router.websocket('/api/threads/{thread_id}/editors/{sid}/service/proxy/{path:path}')
async def proxy_socket(thread_id:str,sid:str,path:str,websocket:WebSocket):
    from websockets.asyncio.client import connect
    origin=urlsplit(websocket.headers.get('origin',''))
    if not origin.netloc or origin.netloc!=websocket.headers.get('host') or origin.scheme not in ('http','https'):
        await websocket.close(code=1008);return
    cookie=websocket.cookies.get('rh_editor','')
    service=next((s for s in list(runtimes.SESSIONS.values()) if s.sid==sid and s.thread==thread_id and s.state=='ready' and not s.closed and secrets.compare_digest(cookie,s.cookie)),None)
    if not service or path.startswith('/') or '..' in path.split('/'):
        await websocket.close(code=1008);return
    backend_path=service.proxy+path if service.document['editor']=='jupyter' else '/'+path
    params=list(websocket.query_params.multi_items())
    if service.document['editor']!='jupyter':params.append(('token',service.token))
    protocols=[p.strip() for p in websocket.headers.get('sec-websocket-protocol','').split(',') if p.strip()]
    try:
        async with connect(service.target.replace('http:','ws:',1)+backend_path+('?' +urlencode(params) if params else ''),additional_headers={'Authorization':'token '+service.token},origin=service.target,subprotocols=protocols or None,proxy=None,max_size=documents.MAX_FILE) as upstream:
            await websocket.accept(subprotocol=upstream.subprotocol)
            async def inbound():
                while True:
                    message=await websocket.receive()
                    if message['type']=='websocket.disconnect':return
                    service.last_seen=time.monotonic()
                    await upstream.send(message.get('bytes') if message.get('bytes') is not None else message.get('text',''))
            async def outbound():
                async for message in upstream:
                    service.last_seen=time.monotonic()
                    if isinstance(message,bytes):await websocket.send_bytes(message)
                    else:await websocket.send_text(message)
            tasks=[asyncio.create_task(inbound()),asyncio.create_task(outbound())]
            try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
    except Exception:
        try:await websocket.close(code=1011)
        except RuntimeError:pass
