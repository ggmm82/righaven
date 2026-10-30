"""Organization Policy Book: readable by the team, managed only by administrators.

Organization sheets follow draft -> active -> retired; each publication is an
immutable version and every change is recorded with its author.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from app.gateway.authz import require_permission
from app.gateway.deps import is_admin_user, require_admin_user
from starlette.concurrency import run_in_threadpool
from .router import same_origin
from . import policy_book

router = APIRouter(prefix='/api/harness/policy-book', tags=['Policy Book'])


async def administrator(request: Request):
    same_origin(request)
    await require_admin_user(request, detail='Il Policy Book è gestito soltanto da un amministratore')
    user = getattr(request.state, 'user', None)
    return str(getattr(user, 'email', None) or getattr(user, 'id', None) or 'amministratore')[:140]


async def run(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('')
@require_permission('agents', 'read')
async def overview(request: Request):
    return {'sheets': await run_in_threadpool(policy_book.overview), 'default_sheet': policy_book.DEFAULT_SHEET,
            'can_manage': await is_admin_user(request)}


@router.get('/sheets/{identifier}')
@require_permission('agents', 'read')
async def detail(identifier: str, request: Request):
    return await run(policy_book.detail, identifier)


@router.put('/sheets/{identifier}/draft')
@require_permission('agents', 'write')
async def save_draft(identifier: str, request: Request):
    actor = await administrator(request)
    return await run(policy_book.save_draft, identifier, await request.json(), actor)


@router.delete('/sheets/{identifier}/draft')
@require_permission('agents', 'write')
async def discard_draft(identifier: str, request: Request):
    actor = await administrator(request)
    return {'sheet': await run(policy_book.discard_draft, identifier, actor)}


class Restore(BaseModel):
    version: int = Field(ge=1)


@router.post('/sheets/{identifier}/{action}')
@require_permission('agents', 'write')
async def lifecycle(identifier: str, action: str, request: Request):
    actor = await administrator(request)
    if action == 'restore':
        try:
            value = Restore.model_validate(await request.json())
        except ValidationError as error:
            raise HTTPException(400, 'Indica la versione da ripristinare') from error
        return await run(policy_book.restore, identifier, value.version, actor)
    operations = {'publish': policy_book.publish, 'retire': policy_book.retire, 'reactivate': policy_book.reactivate}
    if action not in operations:
        raise HTTPException(404, 'Operazione sconosciuta')
    return await run(operations[action], identifier, actor)
