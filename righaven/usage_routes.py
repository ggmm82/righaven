"""Machine usage report: administrators see every user, everyone else their own assignments."""
from fastapi import APIRouter, HTTPException, Request, Response
from app.gateway.authz import require_permission
from app.gateway.deps import is_admin_user
from righaven_core.runtime.user_context import get_effective_user_id
from starlette.concurrency import run_in_threadpool
from . import usage_ledger

router = APIRouter(prefix='/api/harness/usage', tags=['Uso delle macchine'])


@router.get('')
@require_permission('threads', 'read')
async def usage(request: Request, response: Response, days: int = 30):
    response.headers['Cache-Control'] = 'no-store'
    admin = await is_admin_user(request)
    try:
        value = await run_in_threadpool(usage_ledger.report, None if admin else get_effective_user_id(), days)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return {**value, 'scope': 'all' if admin else 'own'}


@router.get('/prices')
@require_permission('threads', 'read')
async def prices(request: Request, response: Response):
    from . import model_prices
    response.headers['Cache-Control'] = 'no-store'
    return {**model_prices.load(), 'can_manage': await is_admin_user(request)}


@router.put('/prices')
@require_permission('threads', 'read')
async def save_prices(request: Request):
    from . import model_prices
    if not await is_admin_user(request):
        raise HTTPException(403, 'Solo un amministratore può impostare i prezzi dei modelli')
    try:
        body = await request.json()
        return await run_in_threadpool(model_prices.save, body)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
