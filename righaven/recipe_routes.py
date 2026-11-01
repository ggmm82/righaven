"""Recipe catalog, user recipe editor and the guided projects started from them."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.gateway.authz import require_permission
from app.gateway.deps import is_admin_user
from righaven_core.runtime.user_context import get_effective_user_id
from starlette.concurrency import run_in_threadpool
from .router import same_origin
from . import recipes

router = APIRouter(prefix='/api/harness/recipes', tags=['Recipes'])


class RecipePhase(BaseModel):
    title: str = Field(max_length=80)
    detail: str = Field(max_length=300)
    checkpoint: bool = True


class RecipeDraft(BaseModel):
    title: str = Field(max_length=80)
    summary: str = Field(max_length=400)
    when: str = Field(max_length=400)
    attach_required: list[str] = Field(default_factory=list, max_length=12)
    attach_optional: list[str] = Field(default_factory=list, max_length=12)
    attach_never: list[str] = Field(default_factory=list, max_length=12)
    questions: list[str] = Field(default_factory=list, max_length=12)
    outputs: list[str] = Field(default_factory=list, max_length=12)
    prerequisites: list[str] = Field(default_factory=list, max_length=12)
    phases: list[RecipePhase] = Field(max_length=12)
    skills: list[str] = Field(max_length=8)
    environment: Optional[str] = Field(default=None, max_length=64)
    tools: list[str] = Field(default_factory=list, max_length=30)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    guidance: str = Field(default='', max_length=2000)
    based_on: Optional[str] = Field(default=None, max_length=40)
    expected_revision: int = Field(default=0, ge=0)


class Sharing(BaseModel):
    shared: bool


async def run(function, *args, code=400):
    try:
        return await run_in_threadpool(function, *args)
    except ValueError as error:
        raise HTTPException(code, str(error)) from error


async def authorized_skills():
    from .capability_policy import native_policy
    return (await run_in_threadpool(native_policy, get_effective_user_id()))['skill_names']


@router.get('')
@require_permission('agents', 'read')
async def catalog(request: Request, locale: str = 'it'):
    return {'recipes': await run_in_threadpool(recipes.catalog, locale, get_effective_user_id()),
            'can_share': await is_admin_user(request)}


def editor_options(user_id):
    """Building blocks for the recipe editor: method skills, tool skills and environments, as one vocabulary."""
    from . import environments as profiles
    from .capability_policy import native_policy
    from .state import applications
    allowed = set(native_policy(user_id)['skill_names'])
    tools = {'skill-' + a['id'] for a in applications()}
    skills = [{'name': s.name, 'description': (s.description or '')[:300], 'kind': 'tool' if s.name in tools else 'method'}
              for s in profiles.skill_inventory(user_id) if s.name in allowed]
    presets = [{k: p[k] for k in ('id', 'name', 'purpose', 'tools', 'skills')} for p in profiles.preset_catalog()]
    return {'skills': sorted(skills, key=lambda s: (s['kind'], s['name'])), 'environments': presets}


@router.get('/editor/options')
@require_permission('agents', 'read')
async def options(request: Request):
    return await run(editor_options, get_effective_user_id())


@router.get('/{identifier}')
@require_permission('agents', 'read')
async def detail(identifier: str, request: Request, locale: str = 'it'):
    return await run(recipes.detail, identifier, locale, get_effective_user_id(), code=404)


@router.get('/{identifier}/draft')
@require_permission('agents', 'read')
async def draft(identifier: str, request: Request, locale: str = 'it'):
    """Editable copy, used to modify a user recipe or duplicate a built-in one."""
    return {'draft': await run(recipes.draft, identifier, locale, get_effective_user_id(), code=404)}


@router.post('')
@require_permission('agents', 'read')
async def create(body: RecipeDraft, request: Request):
    same_origin(request)
    value = body.model_dump(exclude={'expected_revision'})
    return {'recipe': recipes.card(await run(recipes.create, get_effective_user_id(), value, await authorized_skills()), 'it', get_effective_user_id())}


@router.put('/{identifier}')
@require_permission('agents', 'read')
async def update(identifier: str, body: RecipeDraft, request: Request):
    same_origin(request)
    value = body.model_dump(exclude={'expected_revision'})
    saved = await run(recipes.update, get_effective_user_id(), identifier, value, await authorized_skills(), body.expected_revision,
                      await is_admin_user(request), code=409)
    return {'recipe': recipes.card(saved, 'it', get_effective_user_id())}


@router.put('/{identifier}/sharing')
@require_permission('agents', 'read')
async def sharing(identifier: str, body: Sharing, request: Request):
    same_origin(request)
    saved = await run(recipes.share, get_effective_user_id(), identifier, body.shared, await is_admin_user(request), code=403)
    return {'recipe': recipes.card(saved, 'it', get_effective_user_id())}


@router.delete('/{identifier}')
@require_permission('agents', 'read')
async def remove(identifier: str, request: Request):
    same_origin(request)
    await run(recipes.delete, get_effective_user_id(), identifier, await is_admin_user(request), code=403)
    return {'deleted': identifier}

# A guided project is owner-scoped native-thread data, including before the first plan exists.
from righaven_core.utils.thread_id import ThreadId
from righaven_core.config.paths import get_paths
from . import journeys


class GuidedStart(BaseModel):
    recipe_id: str = Field(max_length=40)
    answers: dict[str, str]
    expected_revision: int = Field(default=0, ge=0)


class GuidedDecision(BaseModel):
    stage_id: str = Field(max_length=40)
    approve: bool | None = None
    action: str | None = Field(default=None, pattern='^(approve|revise|skip|reopen|keep)$')
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
        selected_recipe=journeys.definition(body.recipe_id, get_effective_user_id())
    except ValueError as error:
        raise HTTPException(404,str(error)) from error
    if not set(recipes.skills_of(selected_recipe)) <= set(policy['skill_names']):
        raise HTTPException(403, 'Enable the workflow skill before starting this guided project')
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    try:
        result = await run_in_threadpool(journeys.start, workspace, body.recipe_id, body.answers, body.expected_revision, selected_recipe)
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
        result = await run_in_threadpool(journeys.decide, workspace, body.stage_id, body.approve, body.expected_revision, body.note, body.action)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    from .audit_log import append
    action = body.action or ('approve' if body.approve else 'revise')
    append(workspace, 'User', 'Guided phase decision', {'approve': 'approved', 'revise': 'revision', 'skip': 'skipped', 'reopen': 'reopened', 'keep': 'kept'}[action], body.stage_id)
    return {'journey': result}
