"""Use native thread ownership and CSRF for every document operation."""
from pathlib import Path
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import FileResponse,HTMLResponse,Response,StreamingResponse
from pydantic import BaseModel,ConfigDict,Field
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask
from app.gateway.authz import require_permission
from righaven_core.utils.thread_id import ThreadId
from righaven_core.runtime.user_context import get_effective_user_id
from .collaboration_routes import workspace
from .router import same_origin
from . import editor_documents as documents,editor_catalog as catalog,editor_assets as assets

router=APIRouter(tags=['Integrated editors'])


class Start(BaseModel):
    model_config=ConfigDict(extra='forbid')
    path:str=Field(max_length=2000)
    editor:str=Field(max_length=50)
    entry:str=Field(default='',max_length=1000)
    manual:bool=False
    direct:bool=False


class OpenWith(BaseModel):
    model_config=ConfigDict(extra='forbid')
    editor:str=Field(max_length=50)
    manual:bool=False


class Revision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=0)


async def allowed():
    from .capability_policy import native_policy
    return (await run_in_threadpool(native_policy,get_effective_user_id()))['allowed']


def failure(error):return HTTPException(409,str(error))


@router.get('/api/threads/{thread_id}/editors')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def discover(thread_id:ThreadId,request:Request,path:str='',session:str=''):
    policy=await allowed()
    try:
        if session:
            value=await run_in_threadpool(documents.metadata,workspace(thread_id),session,policy)
            choices=[{**row,'source_role':'selected'} for row in catalog.candidates(value['entry'],policy)]
        else:choices=await run_in_threadpool(documents.associations,workspace(thread_id),path,policy) if path else []
        return {'editors':choices,'available_editors':[row for row in catalog.definitions() if not row['tool'] or row['tool'] in policy],
                'sessions':await run_in_threadpool(documents.listing,workspace(thread_id),policy)}
    except ValueError as error:raise failure(error) from error


@router.post('/api/threads/{thread_id}/editors')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def start(thread_id:ThreadId,body:Start,request:Request):
    same_origin(request)
    try:return await run_in_threadpool(documents.start,workspace(thread_id),body.path,body.editor,await allowed(),body.entry,body.manual,body.direct)
    except ValueError as error:raise failure(error) from error


@router.post('/api/threads/{thread_id}/editors/{sid}/open-with')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def open_with(thread_id:ThreadId,sid:str,body:OpenWith,request:Request):
    same_origin(request)
    try:return await run_in_threadpool(documents.open_with,workspace(thread_id),sid,body.editor,await allowed(),body.manual)
    except ValueError as error:raise failure(error) from error


@router.get('/api/threads/{thread_id}/editors/{sid}')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def current(thread_id:ThreadId,sid:str,request:Request):
    try:return await run_in_threadpool(documents.get,workspace(thread_id),sid,await allowed())
    except ValueError as error:raise failure(error) from error


@router.get('/api/threads/{thread_id}/editors/{sid}/files/{name:path}')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def read_file(thread_id:ThreadId,sid:str,name:str,request:Request):
    try:
        stream=await run_in_threadpool(documents.open_file,workspace(thread_id),sid,name,await allowed())
        def chunks():
            with stream:
                while True:
                    chunk=stream.read(65536)
                    if not chunk:break
                    yield chunk
        return StreamingResponse(chunks(),background=BackgroundTask(stream.close),media_type='application/octet-stream',headers={'X-Content-Type-Options':'nosniff','Cache-Control':'no-store','Content-Disposition':'attachment'})
    except ValueError as error:raise failure(error) from error


async def no_service(thread_id,sid):
    from .editor_runtime import find
    value=await run_in_threadpool(documents.metadata,workspace(thread_id),sid,await allowed())
    if value.get('mode')!='project' and find(workspace(thread_id),sid,get_effective_user_id()):raise HTTPException(409,'Close and save the interactive environment before replacing or publishing draft files')


@router.put('/api/threads/{thread_id}/editors/{sid}/files/{name:path}')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def write_file(thread_id:ThreadId,sid:str,name:str,request:Request,expected_revision:int,entry:bool=False):
    same_origin(request);await no_service(thread_id,sid)
    value=await run_in_threadpool(documents.metadata,workspace(thread_id),sid,await allowed())
    if value.get('mode')=='project':
        import tempfile
        with tempfile.NamedTemporaryFile(prefix='righaven-editor-upload-') as staged:
            async for chunk in request.stream():await run_in_threadpool(staged.write,chunk)
            await run_in_threadpool(staged.flush)
            try:return await run_in_threadpool(documents.save_project_file,workspace(thread_id),sid,name,staged.name,expected_revision,await allowed(),entry)
            except ValueError as error:raise failure(error) from error
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>documents.MAX_FILE:raise HTTPException(413,'Document exceeds 64 MiB')
    try:return await run_in_threadpool(documents.save,workspace(thread_id),sid,name,bytes(data),expected_revision,await allowed(),entry)
    except ValueError as error:raise failure(error) from error


@router.post('/api/threads/{thread_id}/editors/{sid}/publish')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def publish(thread_id:ThreadId,sid:str,body:Revision,request:Request):
    same_origin(request);await no_service(thread_id,sid)
    try:return await run_in_threadpool(documents.publish,workspace(thread_id),sid,body.expected_revision,await allowed())
    except ValueError as error:raise failure(error) from error


@router.post('/api/threads/{thread_id}/editors/{sid}/prepare')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def prepare(thread_id:ThreadId,sid:str,request:Request):
    same_origin(request)
    try:
        value=await run_in_threadpool(documents.metadata,workspace(thread_id),sid,await allowed())
        return await run_in_threadpool(assets.request,value['editor'],value['editor_version'])
    except ValueError as error:raise failure(error) from error


@router.get('/api/threads/{thread_id}/editors/{sid}/package')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def package(thread_id:ThreadId,sid:str,request:Request):
    try:
        value=await run_in_threadpool(documents.metadata,workspace(thread_id),sid,await allowed())
        return assets.status(value['editor'],value['editor_version'])
    except ValueError as error:raise failure(error) from error


@router.get('/api/threads/{thread_id}/editors/{sid}/app/{name:path}')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def application_file(thread_id:ThreadId,sid:str,name:str,request:Request):
    try:
        value=await run_in_threadpool(documents.metadata,workspace(thread_id),sid,await allowed());path=assets.file(value['editor'],value['editor_version'],name)
        if name=='index.html':return HTMLResponse(path.read_text().replace('<head>','<head><script src="../bridge.js"></script>',1),headers={'Cache-Control':'no-store'})
        return FileResponse(path,headers={'X-Content-Type-Options':'nosniff','Cache-Control':'private, max-age=3600'})
    except ValueError as error:raise failure(error) from error


@router.get('/api/threads/{thread_id}/editors/{sid}/bridge.js')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def bridge(thread_id:ThreadId,sid:str,request:Request):
    try:
        await run_in_threadpool(documents.metadata,workspace(thread_id),sid,await allowed())
        return Response(Path(__file__).with_name('editor-bridge.js').read_text(),media_type='application/javascript',headers={'Cache-Control':'no-store'})
    except ValueError as error:raise failure(error) from error


class EntryChoice(Revision):
    name:str=Field(min_length=1,max_length=1000)


@router.post('/api/threads/{thread_id}/editors/{sid}/entry')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def choose_entry(thread_id:ThreadId,sid:str,body:EntryChoice,request:Request):
    same_origin(request);await no_service(thread_id,sid)
    try:return await run_in_threadpool(documents.choose_entry,workspace(thread_id),sid,body.name,body.expected_revision,await allowed())
    except ValueError as error:raise failure(error) from error


@router.get('/api/threads/{thread_id}/project-files')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def project_files(thread_id:ThreadId,request:Request,path:str='',query:str='',role:str='all',offset:int=0):
    from .project_files import listing
    try:return await run_in_threadpool(listing,workspace(thread_id),path,query,role,offset)
    except ValueError as error:raise failure(error) from error


class Presence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    client:str=Field(pattern=r'^[a-f0-9-]{36}$')
    active:bool=True


@router.post('/api/threads/{thread_id}/editors/{sid}/presence')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def presence(thread_id:ThreadId,sid:str,body:Presence,request:Request):
    same_origin(request)
    from . import editor_presence,editor_profiles
    policy=await allowed();user=get_effective_user_id()
    try:
        value=await run_in_threadpool(documents.metadata,workspace(thread_id),sid,policy)
        definition=catalog.editor(value['editor'],policy)
        if definition['mode'] in ('service','desktop'):return {'tracked':False}
        profile=value.get('environment_profile')
        if body.active and definition['tool'] and not profile:
            profile=await editor_profiles.ensure(workspace(thread_id),sid,user,request,policy,terminal=True)
        editor_presence.update(user,str(thread_id),sid,profile,value['editor'],body.client,body.active)
        return {'tracked':True}
    except ValueError as error:raise failure(error) from error
