"""Hosting information uses the shared core account, never a parallel identity store."""
from fastapi import APIRouter, Request, HTTPException
from .identity import current_user
from .cloud_portal import current_edition
from pydantic import BaseModel, Field

router = APIRouter(prefix='/api/v1/cloud', tags=['RigHaven hosting'])

@router.get('/edition')
def edition():
    return {'edition': current_edition(), 'is_cloud': current_edition() == 'cloud',
            'is_community': current_edition() == 'community',
            'authentication': '/api/v1/auth', 'hosting_status': 'preview',
            'capabilities': {'private_model_profiles': current_edition() == 'cloud',
                             'job_admission_limits': current_edition() == 'cloud',
                             'shared_organizations': False, 'cloud_oauth_signup': False}}

@router.get('/me')
def me(request: Request):
    user = current_user(request)
    return {'user': {'id': str(user.id), 'email': user.email,
                     'system_role': user.system_role}}

class LimitRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    max_parallel: int = Field(ge=1, le=64)
    jobs_per_month: int = Field(ge=0, le=1000000)

class ProviderRequest(BaseModel):
    engine: str
    model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1, max_length=4096)
    scope: str = 'both'
    base_url: str | None = None

@router.put('/providers')
async def configure_provider(body: ProviderRequest, request: Request):
    current_user(request)
    from .tenant_profiles import save
    try:
        return save(body.engine, body.model, body.api_key, scope=body.scope, base_url=body.base_url)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

@router.get('/providers')
def profiles(request: Request):
    current_user(request)
    from .tenant_profiles import profile
    selected = {}
    for target in ('coordinator', 'squad'):
        try:
            selected[target] = profile(target)
        except ValueError:
            selected[target] = None
    return selected

@router.get('/limits')
def limits(request: Request):
    from .organization_limits import snapshot
    return snapshot(str(current_user(request).id))

@router.put('/limits')
async def configure_limits(body: LimitRequest, request: Request):
    from app.gateway.deps import require_admin_user
    await require_admin_user(request, detail='Only administrators can change organization allowances')
    from .organization_limits import configure
    return configure(body.user_id, body.max_parallel, body.jobs_per_month)

@router.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
def retired_preview(path: str):
    raise HTTPException(410, 'Preview Cloud identity, recovery, vault and quota APIs have been removed. Use the shared /api/v1/auth account API.')
