"""Which build of RigHaven is running: shown on the Overview page after each deployment."""
import os
from pathlib import Path
from fastapi import APIRouter, Request
from app.gateway.authz import require_permission

router = APIRouter(prefix='/api/harness/build', tags=['Build'])


def identity():
    commit = os.getenv('RIGHAVEN_COMMIT', '')
    try:default_version=Path(__file__).resolve().parents[1].joinpath('VERSION').read_text().strip()
    except OSError:default_version='development'
    version=os.getenv('RIGHAVEN_VERSION') or default_version
    return {'version':version, 'commit': commit[:12], 'built_at': os.getenv('RIGHAVEN_BUILT_AT', ''), 'ref': os.getenv('RIGHAVEN_REF', ''),
            'local': not commit}


@router.get('')
@require_permission('agents', 'read')
async def build(request: Request):
    return identity()
