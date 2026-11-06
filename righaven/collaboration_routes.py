"""Owner-scoped shared method, independent of recipes and database connections."""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from app.gateway.authz import require_permission
from righaven_core.config.paths import get_paths
from righaven_core.runtime.user_context import get_effective_user_id
from righaven_core.utils.thread_id import ThreadId
from .router import same_origin
from . import collaboration

router = APIRouter(tags=['Shared method'])


class MethodChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    signature: str = Field(pattern=r'^[0-9a-f]{64}$')
    choice: int = Field(ge=0, le=3)
    note: str = Field(default='', max_length=1500)


def workspace(thread_id):
    return get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())


@router.get('/api/threads/{thread_id}/harness-method')
@require_permission('threads', 'read', owner_check=True, require_existing=True)
async def current(thread_id: ThreadId, request: Request):
    return await run_in_threadpool(collaboration.view, workspace(thread_id))


@router.post('/api/threads/{thread_id}/harness-method/choice')
@require_permission('threads', 'write', owner_check=True, require_existing=True)
async def choose(thread_id: ThreadId, body: MethodChoice, request: Request):
    same_origin(request)
    from .progress_routes import production_running
    if await production_running(request, thread_id):
        raise HTTPException(409, 'Wait for active work to finish before choosing a method')
    from .capability_policy import native_policy
    policy = await run_in_threadpool(native_policy, get_effective_user_id())
    try:
        return await run_in_threadpool(collaboration.choose, workspace(thread_id), body.signature, body.choice, body.note, policy['allowed'])
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get('/api/threads/{thread_id}/harness-method/recipe')
@require_permission('threads', 'read', owner_check=True, require_existing=True)
async def recipe(thread_id: ThreadId, request: Request):
    try:
        return {'draft': await run_in_threadpool(collaboration.recipe_draft, workspace(thread_id))}
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class SourceEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(max_length=2000)
    expected_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    content: str = Field(max_length=1024*1024)


@router.post('/api/threads/{thread_id}/harness-source-edits')
@require_permission('threads', 'write', owner_check=True, require_existing=True)
async def edit_source(thread_id: ThreadId, body: SourceEdit, request: Request):
    same_origin(request)
    from .progress_routes import production_running
    if await production_running(request, thread_id):
        raise HTTPException(409, 'Wait for active work to finish before editing a source')
    from .source_edits import save
    try:
        return await run_in_threadpool(save, workspace(thread_id), body.path, body.expected_sha256, body.content)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


class ObjectiveChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    signature: str = Field(pattern=r'^[0-9a-f]{64}$')
    goal: str = Field(min_length=1,max_length=2000)


@router.get('/api/threads/{thread_id}/harness-objective')
@require_permission('threads','read',owner_check=True,require_existing=True)
async def objective(thread_id: ThreadId,request: Request):
    from .objectives import view
    return await run_in_threadpool(view,workspace(thread_id))


@router.post('/api/threads/{thread_id}/harness-objective')
@require_permission('threads','write',owner_check=True,require_existing=True)
async def change_objective(thread_id: ThreadId,body: ObjectiveChange,request: Request):
    same_origin(request)
    from .progress_routes import production_running
    if await production_running(request,thread_id):
        raise HTTPException(409,'Wait for active work to finish before changing the objective')
    from .objectives import redirect
    try:
        return await run_in_threadpool(redirect,workspace(thread_id),body.goal,body.signature,'owner-api:'+body.signature)
    except ValueError as error:raise HTTPException(409,str(error)) from error
