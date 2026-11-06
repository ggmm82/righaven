"""Authenticated Gallery API, using the shared core session."""
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
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
    user=current_user_id(request)
    try:return gallery.list_packs(category=category, query=q, tag=tag,
        locale=resolve_request_locale(request), user_id=user)
    except ValueError as error:raise HTTPException(422,str(error)) from error

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
    from .router import same_origin
    same_origin(request)
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

class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str = Field(min_length=1, max_length=64)
    body: str = Field(min_length=1, max_length=4000)
    score: int | None = Field(default=None, strict=True, ge=1, le=5)
    parent: str | None = None

class ReasonRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=3, max_length=1000)

@router.get('/packs/{pack_id}/feedback')
def feedback(pack_id: str, request: Request, version: str | None = None,
             offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)):
    from . import gallery_feedback
    try: return gallery_feedback.list_feedback(pack_id, current_user_id(request), version, offset, limit)
    except KeyError as error: raise HTTPException(404, str(error)) from error
    except ValueError as error: raise HTTPException(422, str(error)) from error

@router.post('/packs/{pack_id}/feedback', status_code=201)
def submit_feedback(pack_id: str, body: FeedbackRequest, request: Request):
    from . import gallery_feedback
    from .router import same_origin
    same_origin(request)
    try: return gallery_feedback.write(pack_id, body.version, current_user_id(request), body.body, body.score, body.parent)
    except KeyError as error: raise HTTPException(404, str(error)) from error
    except ValueError as error: raise HTTPException(422, str(error)) from error

@router.delete('/feedback/{key}', status_code=204)
def delete_feedback(key: str, request: Request):
    from . import gallery_feedback
    from .router import same_origin
    same_origin(request)
    gallery_feedback.remove(key, current_user_id(request))

@router.post('/feedback/{key}/report', status_code=204)
def report_feedback(key: str, body: ReasonRequest, request: Request):
    from . import gallery_feedback
    from .router import same_origin
    same_origin(request)
    try: gallery_feedback.report(key, current_user_id(request), body.reason)
    except ValueError as error: raise HTTPException(422, str(error)) from error

@router.get('/feedback-reports')
async def feedback_reports(request: Request):
    from app.gateway.deps import require_admin_user
    await require_admin_user(request, detail='Only administrators can moderate feedback')
    from . import gallery_feedback
    return {'items': gallery_feedback.reports()}

@router.post('/feedback/{key}/moderate', status_code=204)
async def moderate_feedback(key: str, body: ReasonRequest, request: Request):
    from app.gateway.deps import require_admin_user
    from .router import same_origin
    same_origin(request)
    await require_admin_user(request, detail='Only administrators can moderate feedback')
    from . import gallery_feedback
    try: gallery_feedback.moderate(key, body.reason)
    except ValueError as error: raise HTTPException(422, str(error)) from error
