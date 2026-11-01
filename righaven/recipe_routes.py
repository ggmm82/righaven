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
