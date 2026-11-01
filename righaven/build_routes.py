"""Which build of RigHaven is running: shown on the Overview page after each deployment."""
import os
from fastapi import APIRouter, Request
from app.gateway.authz import require_permission

router = APIRouter(prefix='/api/harness/build', tags=['Build'])


def identity():
    commit = os.getenv('RIGHAVEN_COMMIT', '')
    return {'commit': commit[:12], 'built_at': os.getenv('RIGHAVEN_BUILT_AT', ''), 'ref': os.getenv('RIGHAVEN_REF', ''),
            'local': not commit}


@router.get('')
@require_permission('agents', 'read')
async def build(request: Request):
    return identity()
