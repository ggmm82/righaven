"""Recipe catalog for the recipes page and the prefilled chat."""
from fastapi import APIRouter, HTTPException, Request
from app.gateway.authz import require_permission
from starlette.concurrency import run_in_threadpool
from . import recipes

router = APIRouter(prefix='/api/harness/recipes', tags=['Recipes'])


@router.get('')
@require_permission('agents', 'read')
async def catalog(request: Request, locale: str = 'it'):
    return {'recipes': await run_in_threadpool(recipes.catalog, locale)}


@router.get('/{identifier}')
@require_permission('agents', 'read')
async def detail(identifier: str, request: Request, locale: str = 'it'):
    try:
        return await run_in_threadpool(recipes.detail, identifier, locale)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error

# A guided project is owner-scoped native-thread data, including before the first plan exists.
from pydantic import BaseModel, Field
from righaven_core.utils.thread_id import ThreadId
from righaven_core.runtime.user_context import get_effective_user_id
from righaven_core.config.paths import get_paths
from .router import same_origin
from . import journeys


class GuidedStart(BaseModel):
    recipe_id: str = Field(max_length=40)
    answers: dict[str, str]
    expected_revision: int = Field(default=0, ge=0)


class GuidedDecision(BaseModel):
    stage_id: str = Field(max_length=40)
    approve: bool
    expected_revision: int = Field(ge=1)
    note: str = Field(default='', max_length=1500)


journey_router = APIRouter(tags=['Guided projects'])


@journey_router.get('/api/threads/{thread_id}/harness-journey')
@require_permission('threads', 'read', owner_check=True, require_existing=True)
async def guided_view(thread_id: ThreadId, request: Request):
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    return {'journey': await run_in_threadpool(journeys.view, workspace)}


@journey_router.put('/api/threads/{thread_id}/harness-journey')
@require_permission('threads', 'write', owner_check=True, require_existing=True)
async def guided_start(thread_id: ThreadId, body: GuidedStart, request: Request):
    same_origin(request)
    from .capability_policy import native_policy
    policy = await run_in_threadpool(native_policy, get_effective_user_id())
    try:
        selected_recipe=journeys.definition(body.recipe_id)
    except ValueError as error:
        raise HTTPException(404,str(error)) from error
    if selected_recipe['skill'] not in policy['skill_names']:
        raise HTTPException(403, 'Enable the workflow skill before starting this guided project')
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    try:
        result = await run_in_threadpool(journeys.start, workspace, body.recipe_id, body.answers, body.expected_revision)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    from .audit_log import append
    append(workspace, 'User', 'Guided project saved', 'completed', body.recipe_id)
    return {'journey': result}


@journey_router.post('/api/threads/{thread_id}/harness-journey/decision')
@require_permission('threads', 'write', owner_check=True, require_existing=True)
async def guided_decide(thread_id: ThreadId, body: GuidedDecision, request: Request):
    same_origin(request)
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    try:
        result = await run_in_threadpool(journeys.decide, workspace, body.stage_id, body.approve, body.expected_revision, body.note)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    from .audit_log import append
    append(workspace, 'User', 'Guided phase decision', 'approved' if body.approve else 'revision', body.stage_id)
    return {'journey': result}
