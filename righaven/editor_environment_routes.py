"""Editor preparation extends existing native Agent deployment preferences."""
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from righaven_core.utils.thread_id import ThreadId
from starlette.concurrency import run_in_threadpool
from app.gateway.authz import require_permission
from righaven_core.runtime.user_context import get_effective_user_id
from .environment_routes import native_agent
from .router import same_origin
from . import editor_preparation,environments
router=APIRouter(tags=['Environment editors'])

class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    editors:list[str]=Field(max_length=24)

async def tools(request,name):
    agent=await native_agent(request,name);user=get_effective_user_id()
    from .capability_policy import native_policy
    resolved=await run_in_threadpool(environments.resolve_skills,user,agent.skills)
    policy=await run_in_threadpool(native_policy,user,name)
    return sorted(set(resolved['tools'])&set(policy['allowed']))

@router.get('/api/harness/environments/{name}/editors')
@require_permission('agents','read')
async def current(name:str,request:Request):
    return {'editors':editor_preparation.options(get_effective_user_id(),name,await tools(request,name))}

@router.put('/api/harness/environments/{name}/editors')
@require_permission('agents','write')
async def configure(name:str,body:Selection,request:Request):
    same_origin(request);available=await tools(request,name)
    try:return {'editors':await run_in_threadpool(editor_preparation.configure,get_effective_user_id(),name,body.editors,available)}
    except ValueError as error:raise HTTPException(409,str(error)) from error


@router.post('/api/harness/environments/recover-editors')
@require_permission('agents','write')
@require_permission('threads','read')
async def recover_editor_environments(request:Request):
    same_origin(request)
    from .editor_profiles import recover
    from .editor_routes import allowed
    try:return await recover(get_effective_user_id(),request,await allowed())
    except (OSError,ValueError) as error:raise HTTPException(409,str(error)) from error


@router.post('/api/threads/{thread_id}/editors/{sid}/environment')
@require_permission('agents','write')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def save_editor_environment(thread_id:ThreadId,sid:str,request:Request):
    same_origin(request)
    from .editor_profiles import ensure
    from .editor_proxy import authorized
    root,user,policy=await authorized(thread_id,sid)
    try:
        name=await ensure(root,sid,user,request,policy)
        return {'profile':name}
    except ValueError as error:raise HTTPException(409,str(error)) from error
