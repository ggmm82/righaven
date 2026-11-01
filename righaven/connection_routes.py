"""User connections (SQL Server, PostgreSQL, MySQL, Microsoft Entra ID) and their assignment to projects."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from app.gateway.authz import require_permission
from righaven_core.config.paths import get_paths
from righaven_core.runtime.user_context import get_effective_user_id
from righaven_core.utils.thread_id import ThreadId
from .router import same_origin
from . import connections

router = APIRouter(tags=['Connections'])


class Connection(BaseModel):
    id: Optional[str] = Field(default=None, max_length=40)
    kind: Optional[str] = Field(default=None, max_length=20)
    name: str = Field(max_length=80)
    description: str = Field(default='', max_length=400)
    host: Optional[str] = Field(default=None, max_length=253)
    port: Optional[int] = None
    database: Optional[str] = Field(default=None, max_length=128)
    username: Optional[str] = Field(default=None, max_length=128)
    password: Optional[str] = Field(default=None, max_length=512)
    tls: bool = True
    read_only: bool = False
    authentication: str = Field(default='password', max_length=20)
    entra_connection: Optional[str] = Field(default=None, max_length=40)
    tenant_id: Optional[str] = Field(default=None, max_length=120)
    client_id: Optional[str] = Field(default=None, max_length=36)
    client_secret: Optional[str] = Field(default=None, max_length=512)
    cloud: str = Field(default='public', max_length=20)
    mode: Optional[str] = Field(default=None, max_length=20)


class Assignment(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=10)


async def run(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('/api/harness/connections')
@require_permission('agents', 'read')
async def listing(request: Request):
    return {'connections': await run(connections.listing, get_effective_user_id()), 'kinds': list(connections.KINDS)}


@router.post('/api/harness/connections')
@require_permission('agents', 'read')
async def create(body: Connection, request: Request):
    same_origin(request)
    return await run(connections.save, get_effective_user_id(), body.model_dump(exclude_none=True))


@router.put('/api/harness/connections/{identifier}')
@require_permission('agents', 'read')
async def update(identifier: str, body: Connection, request: Request):
    same_origin(request)
    return await run(connections.save, get_effective_user_id(), body.model_dump(exclude_none=True), identifier)


@router.delete('/api/harness/connections/{identifier}')
@require_permission('agents', 'read')
async def remove(identifier: str, request: Request):
    same_origin(request)
    await run(connections.delete, get_effective_user_id(), identifier)
    return {'deleted': identifier}


@router.post('/api/harness/connections/{identifier}/test')
@require_permission('agents', 'read')
async def test(identifier: str, request: Request):
    same_origin(request)
    return await run(connections.test, get_effective_user_id(), identifier)


@router.post('/api/harness/connections/{identifier}/sign-in')
@require_permission('agents', 'read')
async def sign_in(identifier: str, request: Request):
    """Personal Microsoft account: device code flow, with MFA completed on Microsoft's page."""
    same_origin(request)
    return await run(connections.sign_in, get_effective_user_id(), identifier)


@router.post('/api/harness/connections/{identifier}/sign-in/poll')
@require_permission('agents', 'read')
async def sign_in_poll(identifier: str, request: Request):
    same_origin(request)
    return await run(connections.complete_sign_in, get_effective_user_id(), identifier)


@router.delete('/api/harness/connections/{identifier}/sign-in')
@require_permission('agents', 'read')
async def sign_out(identifier: str, request: Request):
    same_origin(request)
    return await run(connections.sign_out, get_effective_user_id(), identifier)


@router.get('/api/threads/{thread_id}/harness-connections')
@require_permission('threads', 'read', owner_check=True, require_existing=True)
async def project_connections(thread_id: ThreadId, request: Request):
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    return {'assigned': await run(connections.assigned, workspace)}


@router.put('/api/threads/{thread_id}/harness-connections')
@require_permission('threads', 'write', owner_check=True, require_existing=True)
async def assign(thread_id: ThreadId, body: Assignment, request: Request):
    same_origin(request)
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    from .audit_log import append
    result = await run(connections.assign, get_effective_user_id(), workspace, body.ids)
    append(workspace, 'Connessioni', 'Connessioni assegnate al lavoro', 'completed', ', '.join(body.ids) or 'nessuna')
    return {'assigned': result}


@router.get('/api/harness/access-catalog')
@require_permission('agents', 'read')
async def access_catalog(request: Request):
    """One discovery surface; existing provider login stores remain authoritative."""
    from .state import connection_status
    import os
    cloud = os.getenv('RIGHAVEN_EDITION', 'community') == 'cloud'
    providers = []
    for engine, label in [('codex', 'OpenAI Codex CLI'), ('gemini', 'Antigravity CLI'), ('claude', 'Anthropic Claude Code CLI'),
                          ('deepseek', 'DeepSeek API'), ('openai', 'OpenAI-compatible API')]:
        # Hosted private keys must not be confused with shared installation credentials.
        providers.append({'id': engine, 'name': label, 'category': 'model', 'scope': 'personal' if cloud else 'installation',
                          'status': 'configure_in_models' if cloud else ('configured' if await run_in_threadpool(connection_status, engine) else 'not_configured'),
                          'manage_url': '/workspace/cloud' if cloud else '/workspace/harness'})
    return {'providers': providers, 'categories': [
        {'id': 'model', 'name': 'AI models and official CLIs', 'available': True},
        {'id': 'database', 'name': 'Databases', 'available': True},
        {'id': 'identity', 'name': 'Microsoft Entra ID', 'available': True},
        {'id': 'api', 'name': 'External APIs', 'available': False},
        {'id': 'storage', 'name': 'Object storage', 'available': False},
        {'id': 'git', 'name': 'Git and deployment targets', 'available': False}],
        'connections_optional': True}
