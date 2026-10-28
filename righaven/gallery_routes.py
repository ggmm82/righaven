"""Authenticated Gallery API, using the shared core session."""
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from . import gallery
from .identity import current_user_id
from .i18n import resolve_request_locale

router = APIRouter(prefix='/api/v1/gallery', tags=['RigHaven Gallery'])

class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

class ForkRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    new_id: str | None = None

class RegistryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str
    sha256: str

@router.get('/registries')
async def registries(request: Request):
    from app.gateway.deps import require_admin_user
    await require_admin_user(request, detail='Only administrators can manage registries')
    from .hub_registry import settings
    return settings()

@router.put('/registries/{name}')
async def configure_registry(name: str, body: RegistryRequest, request: Request):
    from app.gateway.deps import require_admin_user
    await require_admin_user(request, detail='Only administrators can manage registries')
    from .hub_registry import configure
    try: return configure(name, body.url, body.sha256)
    except ValueError as error: raise HTTPException(422, str(error)) from error

@router.post('/registries/{name}/sync')
async def sync_registry(name: str, request: Request):
    from app.gateway.deps import require_admin_user
    from starlette.concurrency import run_in_threadpool
    await require_admin_user(request, detail='Only administrators can manage registries')
    from .hub_registry import sync
    try: return await run_in_threadpool(sync, name)
    except (ValueError, OSError) as error: raise HTTPException(422, str(error)) from error

@router.get('/catalog')
def export_catalog(request: Request):
    current_user_id(request)
    import json, hashlib
    data = json.dumps({'packs': gallery._all_packs()}, sort_keys=True, ensure_ascii=False).encode()
    return Response(data, media_type='application/json', headers={
        'Content-Disposition': 'attachment; filename="righaven-catalog.json"',
        'X-Content-SHA256': hashlib.sha256(data).hexdigest()})

@router.get('/packs')
def list_packs(request: Request, category: str | None = None, q: str | None = None, tag: str | None = None):
    return gallery.list_packs(category=category, query=q, tag=tag,
        locale=resolve_request_locale(request), user_id=current_user_id(request))

@router.get('/packs/{pack_id}')
def get_pack(pack_id: str, request: Request):
    current_user_id(request)
    try: return gallery.get_pack(pack_id, resolve_request_locale(request))
    except KeyError as error: raise HTTPException(404, str(error)) from error

@router.post('/packs/{pack_id}/activate')
async def activate(pack_id: str, request: Request, body: ActivateRequest | None = None):
    user = current_user_id(request)
    try:
        pack = gallery.get_pack(pack_id, resolve_request_locale(request))
        from .pack_activation import install
        installed = await install(pack, user)
        return {**gallery.activate_pack(pack_id, user_id=user, locale=resolve_request_locale(request)),
                'installation': installed}
    except KeyError as error: raise HTTPException(404, str(error)) from error
    except ValueError as error: raise HTTPException(422, str(error)) from error

@router.post('/packs/publish', status_code=201)
async def publish(request: Request):
    user = current_user_id(request)
    try:
        manifest = await request.json()
        manifest['author'] = user
        manifest['verified'] = False
        return gallery.publish_pack(manifest, locale=resolve_request_locale(request))
    except (ValueError, TypeError) as error: raise HTTPException(422, str(error)) from error

@router.post('/packs/{pack_id}/star')
def star(pack_id: str, request: Request):
    return gallery.star_pack(pack_id, current_user_id(request), resolve_request_locale(request))

@router.post('/packs/{pack_id}/fork', status_code=201)
def fork(pack_id: str, body: ForkRequest, request: Request):
    return gallery.fork_pack(pack_id, current_user_id(request), body.new_id, resolve_request_locale(request))
