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
