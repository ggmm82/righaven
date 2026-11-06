"""Agents in the web interface (pair, list, revoke, activity) and the agents' own endpoints.

The agent endpoints sit outside the site password (Caddy's basic_auth in the portable
release, the gateway's own login behind Traefik on Hostinger): the pairing endpoint accepts
only a valid, short-lived pairing code, the connection only a valid agent token, sent in the
X-RigHaven-Agent header (Caddy removes the Authorization header).
"""
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
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
ANDROID = 'https://github.com/{repository}/releases/latest/download/RigHaven-android.apk'


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
        row.update(online=agent_hub.online(row['id']), **{k: v for k, v in agent_hub.state(row['id']).items() if k in ('networks', 'compute')})
    repository = os.getenv('RIGHAVEN_REPOSITORY', 'ggmm82/righaven')
    return {'agents': rows, 'download': DOWNLOAD.format(repository=repository), 'android': ANDROID.format(repository=repository),
            'server': agents.public_address(request)}


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


@router.get('/api/harness/compute-nodes')
@require_permission('agents', 'read')
async def compute_nodes_listing(request: Request):
    """The owner's machines that run on-premise environments, with what they offer and run now."""
    from . import compute_nodes
    return {'nodes': await run(compute_nodes.listing, get_effective_user_id())}


async def _node(request):
    agent = await run_in_threadpool(agents.authenticate, request.headers.get(HEADER, ''))
    if agent is None:
        raise HTTPException(401, 'Agente non autorizzato')
    return agent


@router.get('/api/webhooks/righaven-agent/runs/{name}/bundle')
async def run_bundle(name: str, request: Request):
    """The folders a sandbox of this node mounts (project, output, progress, credentials, connections)."""
    from . import compute_nodes
    agent = await _node(request)
    try:
        path = compute_nodes.bundle(agent['id'], name)
    except LookupError:
        raise HTTPException(404, 'Esecuzione non trovata') from None
    return FileResponse(path, media_type='application/gzip')


@router.get('/api/webhooks/righaven-agent/images/{image:path}')
async def run_image(image: str, request: Request):
    """An environment image for a run of this node, streamed as docker save writes it."""
    import subprocess
    from . import compute_nodes
    agent = await _node(request)
    try:
        compute_nodes.image_for(agent['id'], image)
    except LookupError:
        raise HTTPException(404, 'Immagine non richiesta da questa macchina') from None
    process = subprocess.Popen(['docker', 'save', image], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def chunks():
        try:
            while True:
                data = process.stdout.read(1 << 20)
                if not data:
                    break
                yield data
        finally:
            process.kill()
            process.wait()
    agents.log(agent['user'], agent['id'], 'compute-image', image[:80])
    return StreamingResponse(chunks(), media_type='application/x-tar')


async def _receive(request, handler, name):
    import tempfile
    from . import compute_nodes
    agent = await _node(request)
    with tempfile.TemporaryFile() as stream:
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > compute_nodes.MAX_RESULT:
                raise HTTPException(413, 'Risultato troppo grande')
            stream.write(chunk)
        stream.seek(0)
        try:
            await run_in_threadpool(handler, agent['id'], name, stream)
        except LookupError:
            raise HTTPException(410, 'Esecuzione non più attesa da questo server') from None
        except (ValueError, OSError) as error:
            raise HTTPException(400, str(error)) from error
    return {'ok': True}


@router.put('/api/webhooks/righaven-agent/runs/{name}/live')
async def run_live(name: str, request: Request):
    """Progress of a running sandbox (status and journal of the job), while it runs."""
    from . import compute_nodes
    return await _receive(request, compute_nodes.receive_live, name)


@router.put('/api/webhooks/righaven-agent/runs/{name}/result')
async def run_result(name: str, request: Request):
    """The end of a sandbox: exit code, output, and the folders it was allowed to write."""
    from . import compute_nodes
    return await _receive(request, compute_nodes.receive_result, name)


@router.websocket('/api/webhooks/righaven-agent/connect')
async def connect(websocket: WebSocket):
    """The agent's channel: it stays open while RigHaven Agent runs on the PC."""
    agent = await run_in_threadpool(agents.authenticate, websocket.headers.get(HEADER, ''))
    if agent is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    await agent_hub.serve(websocket, agent)
