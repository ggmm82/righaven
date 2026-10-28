"""REST API routes for the RigHaven Community Gallery (/api/v1/gallery)."""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from . import gallery
from .i18n import resolve_request_locale

if not hasattr(BaseModel, "model_dump"):
    BaseModel.model_dump = lambda self, **kw: self.dict(**kw)

router = APIRouter(prefix='/api/v1/gallery', tags=['RigHaven Community Gallery'])


class ActivateRequest(BaseModel):
    user_id: str = Field(default='default', max_length=64)
    workspace: str | None = Field(default=None, max_length=512)


class ForkRequest(BaseModel):
    author: str = Field(default='community-creator', min_length=1, max_length=64)
    new_id: str | None = Field(default=None, max_length=64)


@router.get('/packs')
def list_gallery_packs(
    request: Request,
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    user_id: str = Query(default='default'),
):
    locale = resolve_request_locale(request)
    try:
        return gallery.list_packs(category=category, query=q, tag=tag, locale=locale, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/packs/{pack_id}')
def get_gallery_pack(pack_id: str, request: Request):
    locale = resolve_request_locale(request)
    try:
        return gallery.get_pack(pack_id, locale=locale)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/packs/{pack_id}/activate')
def activate_gallery_pack(pack_id: str, request: Request, body: ActivateRequest | None = None):
    locale = resolve_request_locale(request)
    payload = body or ActivateRequest()
    try:
        return gallery.activate_pack(
            pack_id,
            user_id=payload.user_id,
            workspace=payload.workspace,
            locale=locale,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/packs/publish', status_code=201)
async def publish_gallery_pack(request: Request):
    locale = resolve_request_locale(request)
    try:
        manifest = await request.json()
        return gallery.publish_pack(manifest, locale=locale)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post('/packs/{pack_id}/star')
def star_gallery_pack(pack_id: str, request: Request, user_id: str = Query(default='default')):
    locale = resolve_request_locale(request)
    try:
        return gallery.star_pack(pack_id, user_id=user_id, locale=locale)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post('/packs/{pack_id}/fork', status_code=201)
def fork_gallery_pack(pack_id: str, body: ForkRequest, request: Request):
    locale = resolve_request_locale(request)
    try:
        return gallery.fork_pack(pack_id, author=body.author, new_id=body.new_id, locale=locale)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
