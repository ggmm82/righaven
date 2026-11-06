"""Agents in the web interface (pair, list, revoke, activity) and the agents' own endpoints.

The agent endpoints sit outside the site password of the proxy: the pairing endpoint accepts
only a valid, short-lived pairing code, the connection only a valid agent token, sent in the
X-RigHaven-Agent header (the proxy removes the Authorization header).
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from app.gateway.authz import require_permission
from righaven_core.runtime.user_context import get_effective_user_id

from . import agent_hub, agents
from .router import same_origin

router = APIRouter()
HEADER = 'x-righaven-agent'
MAX_CAPTURE = 64 << 20
DOWNLOAD = 'https://github.com/{repository}/releases/latest/download/RigHaven-Agent-windows-x64.exe'


async def run(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error


class Pairing(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class Redeem(BaseModel):
    code: str = Field(min_length=4, max_length=20)
    platform: str = Field(default='', max_length=20)
    version: str = Field(default='', max_length=40)


@router.get('/api/harness/agents')
@require_permission('agents', 'read')
async def listing(request: Request):
    """This user's agents, whether they are connected now, and where to download RigHaven Agent."""
    rows = await run(agents.listing, get_effective_user_id())
    for row in rows:
        row.update(online=agent_hub.online(row['id']), **{k: v for k, v in agent_hub.state(row['id']).items() if k in ('networks',)})
    return {'agents': rows, 'download': DOWNLOAD.format(repository=os.getenv('RIGHAVEN_REPOSITORY', 'ggmm82/righaven')),
            'server': str(request.base_url).rstrip('/')}


@router.post('/api/harness/agents/pairings')
@require_permission('agents', 'write')
async def pairing(body: Pairing, request: Request):
    """A code, valid ten minutes, that RigHaven Agent exchanges once for its own access."""
    same_origin(request)
    return await run(agents.create_code, get_effective_user_id(), body.name)


@router.delete('/api/harness/agents/{identifier}')
@require_permission('agents', 'write')
async def revoke(identifier: str, request: Request):
    same_origin(request)
    result = await run(agents.revoke, get_effective_user_id(), identifier)
    session = agent_hub.SESSIONS.get(identifier)
    if session is not None:
        try:
            await session.websocket.close(code=4001)
        except Exception:
            pass
    return result


@router.get('/api/harness/agents/activity')
@require_permission('agents', 'read')
async def activity(request: Request, agent: Optional[str] = None):
    """What was asked to this user's agents: searches, actions on the PC, tunnels, connections."""
    return {'activity': await run(agents.activity, get_effective_user_id(), agent)}


@router.post('/api/webhooks/righaven-agent/pair')
async def redeem(body: Redeem):
    """Called by RigHaven Agent with the code the owner typed: returns the agent's token, once."""
    return await run(agents.redeem, body.code, body.platform, body.version)


@router.put('/api/webhooks/righaven-agent/capture')
async def capture(request: Request):
    """The last traffic recording of an agent (pcapng), for the owner to download."""
    agent = await run_in_threadpool(agents.authenticate, request.headers.get(HEADER, ''))
    if agent is None:
        raise HTTPException(401, 'Agente non autorizzato')
    folder = agents.folder(agent['id'])
    temporary = folder / 'capture.pcapng.new'
    size = 0
    with temporary.open('wb') as stream:
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_CAPTURE:
                stream.close()
                temporary.unlink()
                raise HTTPException(413, 'Registrazione troppo grande (al massimo 64 MiB)')
            stream.write(chunk)
    temporary.replace(folder / 'capture.pcapng')
    agents.log(agent['user'], agent['id'], 'capture-upload', str(size) + ' bytes')
    return {'ok': True, 'size': size}


@router.websocket('/api/webhooks/righaven-agent/connect')
async def connect(websocket: WebSocket):
    """The agent's channel: it stays open while RigHaven Agent runs on the PC."""
    agent = await run_in_threadpool(agents.authenticate, websocket.headers.get(HEADER, ''))
    if agent is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    await agent_hub.serve(websocket, agent)
