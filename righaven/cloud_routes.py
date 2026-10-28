"""REST API routes for RigHaven Cloud Portal & Dual Edition (/api/v1/cloud)."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from . import cloud_portal as cloud
from .i18n import resolve_request_locale

if not hasattr(BaseModel, "model_dump"):
    BaseModel.model_dump = lambda self, **kw: self.dict(**kw)

router = APIRouter(prefix='/api/v1/cloud', tags=['RigHaven Cloud Portal'])


class SignUpRequest(BaseModel):
    username: str = Field(min_length=3, max_length=48)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    locale: str = Field(default='en', max_length=8)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class OAuthRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str = Field(min_length=5, max_length=120)
    locale: str = Field(default='en', max_length=8)


class RecoverRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    new_password: str | None = Field(default=None, max_length=128)


class OnboardingRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=48)
    locale: str = Field(default='en', max_length=8)
    default_engine: str = Field(default='deepseek', max_length=32)
    starter_pack_id: str = Field(default='env-architecture-modeling-rig', max_length=64)


class VaultKeyRequest(BaseModel):
    api_key: str = Field(min_length=6, max_length=512)


class UsageRecordRequest(BaseModel):
    sandbox_minutes: float = Field(default=0.0, ge=0.0)
    storage_bytes: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    job_id: str | None = Field(default=None, max_length=64)


def _current_user_id(request: Request) -> str:
    auth = request.headers.get('authorization', '')
    if auth.lower().startswith('bearer '):
        token = auth.split(' ', 1)[1].strip()
        try:
            return cloud.verify_jwt(token)['sub']
        except ValueError as exc:
            raise HTTPException(401, str(exc)) from exc
    raise HTTPException(401, 'Bearer JWT token required')


@router.get('/edition')
def get_edition():
    return cloud.edition_info()


@router.post('/auth/signup', status_code=201)
def signup(body: SignUpRequest, request: Request):
    locale = body.locale or resolve_request_locale(request)
    try:
        return cloud.signup_user(body.username, body.email, body.password, locale=locale)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/auth/login')
def login(body: LoginRequest):
    try:
        return cloud.login_user(body.identifier, body.password)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.post('/auth/oauth/{provider}')
def oauth_callback(provider: str, body: OAuthRequest, request: Request):
    locale = body.locale or resolve_request_locale(request)
    try:
        return cloud.oauth_login(provider, body.username, body.email, locale=locale)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/auth/recover')
def recover_account(body: RecoverRequest):
    try:
        return cloud.recover_password(body.email, body.new_password)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/onboarding')
def onboarding(body: OnboardingRequest):
    try:
        return cloud.complete_onboarding(
            body.user_id,
            locale=body.locale,
            default_engine=body.default_engine,
            starter_pack_id=body.starter_pack_id,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/me')
def get_profile(request: Request):
    user_id = _current_user_id(request)
    return {
        'user': cloud.get_user(user_id),
        'quotas': cloud.get_tenant_quotas(user_id),
        'vault': cloud.list_vault_keys(user_id),
    }


@router.get('/workspace')
def get_workspace(request: Request):
    user_id = _current_user_id(request)
    user = cloud.get_user(user_id)
    from . import gallery
    return {
        'user_id': user_id,
        'workspace_path': user['workspace_path'],
        'active_gallery_packs': gallery.active_packs_for(user_id),
        'quotas': cloud.get_tenant_quotas(user_id),
    }


@router.get('/vault')
def list_vault(request: Request):
    user_id = _current_user_id(request)
    return cloud.list_vault_keys(user_id)


@router.put('/vault/{provider}')
def save_vault_key(provider: str, body: VaultKeyRequest, request: Request):
    user_id = _current_user_id(request)
    try:
        return cloud.store_vault_key(user_id, provider, body.api_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete('/vault/{provider}')
def remove_vault_key(provider: str, request: Request):
    user_id = _current_user_id(request)
    return cloud.delete_vault_key(user_id, provider)


@router.get('/quotas')
def get_quotas(request: Request):
    user_id = _current_user_id(request)
    return cloud.get_tenant_quotas(user_id)


@router.post('/quotas/record')
def record_usage(body: UsageRecordRequest, request: Request):
    user_id = _current_user_id(request)
    return cloud.record_tenant_usage(
        user_id,
        sandbox_minutes=body.sandbox_minutes,
        storage_bytes=body.storage_bytes,
        tokens=body.tokens,
        job_id=body.job_id,
    )


@router.get('/creators/{username}')
def creator_profile(username: str, request: Request):
    locale = resolve_request_locale(request)
    return cloud.get_creator_profile(username, locale=locale)
