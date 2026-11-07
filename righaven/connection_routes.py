"""User connections (databases, Microsoft Entra ID, devices) and their assignment to projects."""
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
    host: Optional[str] = Field(default=None, max_length=1000)
    port: Optional[int] = None
    database: Optional[str] = Field(default=None, max_length=128)
    username: Optional[str] = Field(default=None, max_length=254)
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
    access: Optional[str] = Field(default=None, max_length=10)
    write_schema: Optional[str] = Field(default=None, max_length=128)
    transport: Optional[str] = Field(default=None, max_length=10)
    protocol: Optional[str] = Field(default=None, max_length=20)
    device: Optional[str] = Field(default=None, max_length=160)
    topic: Optional[str] = Field(default=None, max_length=200)
    path: Optional[str] = Field(default=None, max_length=300)
    unit: Optional[int] = None
    baud: Optional[int] = None
    version: Optional[str] = Field(default=None, max_length=4)
    node_id: Optional[int] = None
    address: Optional[str] = Field(default=None, max_length=17)
    agent: Optional[str] = Field(default=None, max_length=20)
    ranges: Optional[list[str]] = Field(default=None, max_length=64)
    exclude: Optional[list[str]] = Field(default=None, max_length=64)
    authorized: Optional[bool] = None


class DeviceDecision(BaseModel):
    decision: str = Field(max_length=10)


class Assignment(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=10)
    write: list[str] = Field(default_factory=list, max_length=10)
    deferred: list[str]|None = Field(default=None,max_length=10)


async def run(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get('/api/harness/connections')
@require_permission('agents', 'read')
async def listing(request: Request):
    return {'connections': await run(connections.listing, get_effective_user_id()), 'kinds': list(connections.KINDS),
            'devices': connections.local_devices(), 'protocols': list(connections.PROTOCOLS), 'bauds': list(connections.BAUDS)}


class Discovery(BaseModel):
    network: str = Field(max_length=43)
    agent: Optional[str] = Field(default=None, max_length=20)


class Identify(BaseModel):
    devices: list = Field(default_factory=list, max_length=4096)


class Explore(BaseModel):
    address: str = Field(max_length=45)
    agent: Optional[str] = Field(default=None, max_length=20)


async def pc(request: Request, agent: Optional[str]):
    """The PC an action is about: an agent of this user, or (no agent) the PC of this server, for administrators only.

    Returns the agent ID, None for the local PC, or raises 403/404."""
    if agent:
        from . import agents
        try:
            await run_in_threadpool(agents.owned, get_effective_user_id(), agent)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error
        return agent
    from app.gateway.deps import is_admin_user
    if not await is_admin_user(request):
        raise HTTPException(403, 'Solo un amministratore può usare il PC su cui gira RigHaven: collega il tuo PC con RigHaven Agent')
    return None


async def reports(request: Request, agent: Optional[str]):
    """Where the searches of this PC are kept, or None when this user may not see them."""
    try:
        target = await pc(request, agent)
    except HTTPException:
        return False
    if target is None:
        return None
    from . import agents
    return str(agents.folder(target))


@router.get('/api/harness/connections/discovery')
@require_permission('agents', 'read')
async def discovery(request: Request, agent: Optional[str] = None):
    """The PC's local networks (from the portable launcher or an agent) and the ports a search tries."""
    from . import device_discovery
    folder = await reports(request, agent)
    networks = device_discovery.local_networks()
    if agent and folder:
        from . import agent_hub
        networks = agent_hub.state(agent).get('networks', [])
    if folder is False:
        return {'networks': [], 'ports': sorted(device_discovery.PORTS), 'allowed': device_discovery.private_allowed(),
                'bluetooth': None, 'serial': [], 'wifi': None}
    return {'networks': networks, 'ports': sorted(device_discovery.PORTS),
            'allowed': device_discovery.private_allowed() or bool(agent), 'bluetooth': await run(device_discovery.bluetooth, folder),
            'serial': await run(device_discovery.serial_ports, folder), 'wifi': await run(device_discovery.wifi, folder)}


@router.get('/api/harness/connections/discovery/ble-history.csv')
@require_permission('agents', 'read')
async def ble_history(request: Request, agent: Optional[str] = None):
    """Readings of Bluetooth LE sensors heard by the launcher (RigHaven.exe bluetooth N), as CSV."""
    from fastapi.responses import Response
    from . import device_discovery
    target = await pc(request, agent)
    folder = None
    if target:
        from . import agents
        folder = str(agents.folder(target))
    body = await run(device_discovery.ble_history_csv, folder)
    return Response(body, media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="bluetooth-sensors.csv"'})


@router.get('/api/harness/connections/discovery/capture.pcapng')
@require_permission('agents', 'read')
async def traffic_capture(request: Request, agent: Optional[str] = None):
    """The last traffic recording of the PC (pktmon), for Wireshark: administrators for this server's PC, the owner for an agent."""
    from fastapi.responses import FileResponse
    from . import device_discovery
    target = await pc(request, agent)
    folder = None
    if target:
        from . import agents
        folder = str(agents.folder(target))
    path = await run(device_discovery.capture_file, folder)
    return FileResponse(path, media_type='application/vnd.tcpdump.pcap', filename='righaven-traffic.pcapng')


class HostRequest(BaseModel):
    action: str = Field(max_length=30)
    args: dict = Field(default_factory=dict)
    agent: Optional[str] = Field(default=None, max_length=20)


@router.get('/api/harness/host')
@require_permission('agents', 'read')
async def host_state(request: Request, agent: Optional[str] = None):
    """Whether the launcher on the PC (or the given agent) answers, and the actions it can carry out there."""
    from . import host_bridge
    try:
        target = await pc(request, agent)
    except HTTPException:
        return {'connected': False, 'platform': '', 'actions': [], 'allowed': False}
    return {**await run(host_bridge.state, target), 'allowed': True}


@router.post('/api/harness/host/requests')
@require_permission('agents', 'write')
async def host_request(body: HostRequest, request: Request):
    """An action on the PC asked from the page (Bluetooth search, USB, COM ports, Matter)."""
    same_origin(request)
    from . import host_bridge
    if body.action in host_bridge.APPROVED_ONLY:
        raise HTTPException(400, 'Questa azione scrive su un dispositivo: chiedila nella chat, serve la tua approvazione nella scheda del compito')
    target = await pc(request, body.agent)
    return await run(host_bridge.request, body.action, body.args, target)


@router.get('/api/harness/host/requests/{identifier}')
@require_permission('agents', 'read')
async def host_result(identifier: str, request: Request):
    from . import agent_hub, host_bridge
    job = agent_hub.JOBS.get(identifier)
    await pc(request, job['agent'] if job else None)
    return await run(host_bridge.result, identifier)


class MatterCode(BaseModel):
    code: str = Field(max_length=120)


class MatterCommand(BaseModel):
    endpoint: int = Field(ge=0, le=65534)
    command: str = Field(max_length=10)


@router.get('/api/harness/matter')
@require_permission('agents', 'read')
async def matter_status(request: Request):
    """The optional Matter controller and the devices it controls."""
    from . import matter
    return await run(matter.status)


@router.post('/api/harness/matter/commission')
@require_permission('agents', 'write')
async def matter_commission(body: MatterCode, request: Request):
    """Join a Matter device shared from another app with its pairing code (on the network)."""
    same_origin(request)
    from . import matter
    return await run(matter.commission, body.code)


@router.post('/api/harness/matter/nodes/{node_id}/command')
@require_permission('agents', 'write')
async def matter_command(node_id: int, body: MatterCommand, request: Request):
    """A command the owner gives from the page (On, Off, Toggle)."""
    same_origin(request)
    from . import matter
    return await run(matter.command, node_id, body.endpoint, body.command)


@router.delete('/api/harness/matter/nodes/{node_id}')
@require_permission('agents', 'write')
async def matter_remove(node_id: int, request: Request):
    same_origin(request)
    from . import matter
    return await run(matter.remove, node_id)


@router.post('/api/harness/connections/discovery/explore')
@require_permission('agents', 'read')
async def explore(body: Explore, request: Request):
    """One address chosen by the owner: ports, name, home page. Nothing is written."""
    same_origin(request)
    from . import device_discovery
    if body.agent:
        agent = await pc(request, body.agent)
        return await run(device_discovery.explore_from_agent, agent, body.address)
    return await run(device_discovery.explore, body.address)


@router.post('/api/harness/connections/discovery')
@require_permission('agents', 'read')
async def discover(body: Discovery, request: Request):
    """Search one private network chosen by the owner: TCP connection attempts only, nothing is written."""
    same_origin(request)
    from . import device_discovery
    if body.agent:
        agent = await pc(request, body.agent)
        return await run(device_discovery.scan_from_agent, agent, body.network)
    return await run(device_discovery.scan, body.network)


@router.post('/api/harness/connections/discovery/identify')
@require_permission('agents', 'read')
async def identify(body: Identify, request: Request):
    """What an agent's network search found, identified as a search from this server. The page runs
    the search itself (start and poll), since a phone needs longer than a proxy waits for one answer."""
    same_origin(request)
    from . import device_discovery
    return {'devices': await run(device_discovery.identified, body.devices)}


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


@router.post('/api/harness/connections/{identifier}/databases')
@require_permission('agents', 'read')
async def databases(identifier: str, request: Request):
    """Databases the signed-in Microsoft account can see on this server, to choose one without typing it."""
    same_origin(request)
    return await run(connections.databases, get_effective_user_id(), identifier)


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
    result = await run(connections.assign, get_effective_user_id(), workspace, body.ids, body.write,body.deferred)
    append(workspace, 'Connessioni', 'Connessioni assegnate al lavoro', 'completed', (', '.join(body.ids) or 'nessuna')
           + (' · scrittura consentita: ' + ', '.join(body.write) if body.write else '')
           + (' · destinazioni rimandate dall’utente: '+', '.join(body.deferred) if body.deferred else ''))
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
                          ('openai', 'OpenAI-compatible API (OpenAI, DeepSeek, Kimi, OpenRouter…)')]:
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


@router.get('/api/threads/{thread_id}/device-changes')
@require_permission('threads', 'read', owner_check=True, require_existing=True)
async def device_changes(thread_id: ThreadId, request: Request):
    """Reprogramming the coordinator asked for: each one waits for the owner's decision."""
    from . import device_changes as changes
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    return {'changes': await run(changes.listing, workspace)}


@router.post('/api/threads/{thread_id}/device-changes/{identifier}')
@require_permission('threads', 'write', owner_check=True, require_existing=True)
async def decide_device_change(thread_id: ThreadId, identifier: str, body: DeviceDecision, request: Request):
    same_origin(request)
    from . import device_changes as changes
    workspace = get_paths().sandbox_user_data_dir(thread_id, user_id=get_effective_user_id())
    return await run(changes.decide, workspace, identifier, body.decision)
