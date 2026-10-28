"""Hosting information uses the shared core account, never a parallel identity store."""
from fastapi import APIRouter, Request, HTTPException
from .identity import current_user
from .cloud_portal import current_edition

router = APIRouter(prefix='/api/v1/cloud', tags=['RigHaven hosting'])

@router.get('/edition')
def edition():
    return {'edition': current_edition(), 'is_cloud': current_edition() == 'cloud',
            'is_community': current_edition() == 'community',
            'authentication': '/api/v1/auth', 'hosting_status': 'preview',
            'capabilities': {'multi_tenant_workspaces': False,
                             'resource_quotas': False, 'cloud_oauth_signup': False}}

@router.get('/me')
def me(request: Request):
    user = current_user(request)
    return {'user': {'id': str(user.id), 'email': user.email,
                     'system_role': user.system_role}}

@router.api_route('/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'])
def retired_preview(path: str):
    raise HTTPException(410, 'Preview Cloud identity, recovery, vault and quota APIs have been removed. Use the shared /api/v1/auth account API.')
