"""Organization Policy Book: readable by the team, edited only by administrators."""
from fastapi import APIRouter, HTTPException, Request
from app.gateway.authz import require_permission
from app.gateway.deps import require_admin_user
from starlette.concurrency import run_in_threadpool
from .router import same_origin
from . import policy_book

router = APIRouter(prefix='/api/harness/policy-book', tags=['Policy Book'])


@router.get('')
@require_permission('agents', 'read')
async def sheets(request: Request):
    return {'sheets': await run_in_threadpool(policy_book.book), 'default_sheet': policy_book.DEFAULT_SHEET}


@router.put('/sheets/{identifier}')
@require_permission('agents', 'write')
async def save(identifier: str, request: Request):
    same_origin(request)
    await require_admin_user(request, detail='Il Policy Book è modificabile soltanto da un amministratore')
    value = await request.json()
    if not isinstance(value, dict) or value.get('id', identifier) != identifier:
        raise HTTPException(400, 'L’id della sheet deve coincidere con l’indirizzo')
    try:
        return await run_in_threadpool(policy_book.save, {**value, 'id': identifier})
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.delete('/sheets/{identifier}')
@require_permission('agents', 'write')
async def delete(identifier: str, request: Request):
    same_origin(request)
    await require_admin_user(request, detail='Il Policy Book è modificabile soltanto da un amministratore')
    try:
        await run_in_threadpool(policy_book.delete, identifier)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return {'deleted': identifier}
