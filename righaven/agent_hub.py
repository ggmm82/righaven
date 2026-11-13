"""Live agents: the WebSocket each agent keeps open towards the server, the actions sent to it and
the tunnels that carry a serial port or a home-network device of the agent to the server's workers.

Protocol (JSON text frames, binary frames for tunnel data):
  agent  → server  {"type": "hello", "platform", "version", "actions": [...]}
  server → agent   {"type": "request", "id", "action", "args"}
  agent  → server  {"type": "result", "id", "result"}          (an "error" key marks a failure)
  server → agent   {"type": "open", "stream", "target"}        target "com:COM5" or "tcp:192.168.1.44:6668"
  agent  → server  {"type": "opened", "stream"} / {"type": "close", "stream", "error"?}
  both             binary: 4-byte big-endian stream number, then the bytes
Compute nodes (an agent with Docker that runs sandboxes for this server, see compute_nodes):
  agent  → server  "hello" and {"type": "compute", ...} carry "compute": {"cpus", "memory_mib", "jobs", "docker"}
  server → agent   {"type": "run", "id", "args", "mounts", "timeout"} / {"type": "stop", "id"}
  agent  → server  {"type": "run-state", "id", "state"}; files travel over HTTP (agent_routes)
The gateway runs as one process, so the sessions live in memory.
"""
import asyncio
import json
import re
import socket
import struct
import threading
import time
import uuid

from . import agents

PROTOCOL = 1
JOB_SECONDS = 86400
TUNNEL_PORTS = range(42000, 43000)
MAX_FRAME = 1 << 20

_lock = threading.RLock()
SESSIONS = {}   # agent id → Session
JOBS = {}       # job id → {'agent', 'action', 'status', 'result', 'at'}
TUNNELS = {}    # (agent id, target) → (server, port)
ACTIVE = {}  # (agent, target) → tunnel clients connected now
LOOP = None


class Session:
    def __init__(self, agent, websocket, loop):
        self.agent, self.websocket, self.loop = agent, websocket, loop
        self.platform, self.version, self.actions = agent.get('platform', ''), agent.get('version', ''), []
        self.networks = []
        self.compute = None  # what a compute node offers: cpus, memory_mib, jobs, docker
        self.streams = {}  # stream number → asyncio.StreamWriter
        self.opened = {}   # stream number → asyncio.Event
        self.next_stream = 1
        self.send_lock = asyncio.Lock()

    async def send_json(self, value):
        async with self.send_lock:
            await self.websocket.send_text(json.dumps(value))

    async def send_bytes(self, stream, data):
        async with self.send_lock:
            await self.websocket.send_bytes(struct.pack('>I', stream) + data)


def _clean_jobs():
    now = time.time()
    for key in [k for k, v in JOBS.items() if v['at'] < now - JOB_SECONDS]:
        JOBS.pop(key, None)


def online(identifier):
    with _lock:
        return identifier in SESSIONS


def state(identifier):
    with _lock:
        session = SESSIONS.get(identifier)
        if session is None:
            return {'connected': False, 'platform': '', 'actions': [], 'matter': False}
        return {'connected': True, 'platform': session.platform, 'actions': list(session.actions), 'matter': False,
                'version': session.version, 'networks': list(session.networks), 'compute': dict(session.compute) if session.compute else None}


IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}')


def compute(value):
    """The capacity a compute node declares, within sane bounds; None when it runs no sandboxes."""
    if not isinstance(value, dict):
        return None
    try:
        cpus, memory, jobs = float(value.get('cpus')), int(value.get('memory_mib')), int(value.get('jobs') or 1)
    except (TypeError, ValueError):
        return None
    if not (0.25 <= cpus <= 1024 and 512 <= memory <= 16 << 20 and 1 <= jobs <= 64):
        return None
    result = {'cpus': round(cpus, 3), 'memory_mib': memory, 'jobs': jobs, 'docker': str(value.get('docker') or '')[:40],
              'running': max(0, min(64, int(value.get('running') or 0)))}
    # The environment images the node keeps (it prepares them itself and removes the least used).
    if isinstance(value.get('images'), list):
        result['images'] = [i for i in value['images'][:1000] if isinstance(i, str) and IMAGE_ID.fullmatch(i)]
    return result


def note_image(identifier, image_id):
    """An image the node has just prepared, known before its next report."""
    with _lock:
        session = SESSIONS.get(identifier)
        if session is not None and session.compute is not None and image_id not in session.compute.setdefault('images', []):
            session.compute['images'].append(image_id)


def owner(identifier):
    with _lock:
        session = SESSIONS.get(identifier)
    return session.agent['user'] if session else ''


def send(identifier, message):
    """A message to an agent, from a worker thread."""
    with _lock:
        session = SESSIONS.get(identifier)
    if session is None:
        raise ValueError('L’agente non è collegato: avvia RigHaven Agent sul PC')
    asyncio.run_coroutine_threadsafe(session.send_json(message), session.loop).result(timeout=15)


def request(identifier, action, args):
    """Queue an action for an agent (called from worker threads)."""
    with _lock:
        session = SESSIONS.get(identifier)
        if session is None:
            raise ValueError('L’agente non è collegato: avvia RigHaven Agent sul PC')
        if action not in session.actions:
            raise ValueError('Questa azione non è disponibile su questo agente')
        _clean_jobs()
        job = uuid.uuid4().hex
        JOBS[job] = {'agent': identifier, 'action': action, 'status': 'running', 'result': None, 'at': time.time()}
    message = {'type': 'request', 'id': job, 'action': action, 'args': args}
    asyncio.run_coroutine_threadsafe(session.send_json(message), session.loop).result(timeout=15)
    agents.log(session.agent['user'], identifier, action, json.dumps({k: v for k, v in args.items() if k not in ('password', 'key')})[:200], 'asked')
    return {'id': job, 'status': 'queued'}


def result(job):
    with _lock:
        entry = JOBS.get(job)
        if entry is None:
            return None
        return {'id': job, 'status': entry['status'], **({'result': entry['result']} if entry['result'] is not None else {})}


def _store_report(identifier, action, value):
    """Searches of an agent are kept like the launcher's discovery reports, for the page and the chat."""
    if not isinstance(value, dict) or value.get('error'):
        return
    names = {'bluetooth-scan': 'bluetooth.json', 'wifi-scan': 'wifi.json', 'com-share': None}
    name = names.get(action)
    if not name:
        return
    report = {'scanned_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    if action == 'bluetooth-scan':
        report.update(devices=value.get('devices') or [], warnings=value.get('warnings') or [])
    else:
        report.update(networks=value.get('networks') or [])
    from .state import atomic_json
    atomic_json(agents.folder(identifier) / name, report)


async def serve(websocket, agent):
    """One agent's connection, for as long as it stays open."""
    global LOOP
    LOOP = asyncio.get_running_loop()
    session = Session(agent, websocket, LOOP)
    with _lock:
        previous = SESSIONS.get(agent['id'])
        SESSIONS[agent['id']] = session
    if previous is not None:
        try:
            await previous.websocket.close(code=4000)
        except Exception:
            pass
    agents.log(agent['user'], agent['id'], 'connected', agent.get('name', ''))
    try:
        while True:
            message = await websocket.receive()
            if message.get('type') == 'websocket.disconnect':
                break
            if message.get('bytes') is not None:
                data = message['bytes']
                if len(data) < 4 or len(data) > MAX_FRAME:
                    continue
                writer = session.streams.get(struct.unpack('>I', data[:4])[0])
                if writer is not None:
                    writer.write(data[4:])
                    await writer.drain()
                continue
            try:
                value = json.loads(message.get('text') or '')
            except ValueError:
                continue
            kind = value.get('type')
            if kind == 'hello':
                session.platform = str(value.get('platform') or '')[:20]
                session.version = str(value.get('version') or '')[:40]
                session.actions = [str(a)[:30] for a in value.get('actions') or []][:60]
                from .device_discovery import network as private_network
                session.networks = []
                for item in (value.get('networks') or [])[:8]:
                    try:
                        session.networks.append(str(private_network(item)))
                    except ValueError:
                        continue
                session.compute = compute(value.get('compute'))
                agents.seen(agent['id'], session.platform, session.version, session.actions)
                await session.send_json({'type': 'welcome', 'protocol': PROTOCOL, 'agent': agent['id'], 'name': agent.get('name', '')})
            elif kind == 'result':
                job, outcome = str(value.get('id')), value.get('result')
                with _lock:
                    entry = JOBS.get(job)
                    if entry is None or entry['agent'] != agent['id']:
                        continue
                    failed = isinstance(outcome, dict) and bool(outcome.get('error'))
                    entry.update(status='failed' if failed else 'done', result=outcome if isinstance(outcome, dict) else {'value': outcome})
                if not failed:
                    _store_report(agent['id'], entry['action'], outcome)
                agents.log(agent['user'], agent['id'], entry['action'], str(outcome.get('error', ''))[:200] if failed else '', 'failed' if failed else 'done')
            elif kind == 'opened':
                event = session.opened.get(value.get('stream'))
                if event is not None:
                    event.set()
            elif kind == 'close':
                writer = session.streams.pop(value.get('stream'), None)
                event = session.opened.pop(value.get('stream'), None)
                if event is not None:
                    event.set()
                if writer is not None:
                    writer.close()
            elif kind == 'compute':
                session.compute = compute(value)
            elif kind == 'run-output':
                from . import compute_nodes
                compute_nodes.output(agent['id'], str(value.get('id') or ''), str(value.get('text') or '')[:65536])
            elif kind == 'run-state':
                from . import compute_nodes
                compute_nodes.started(agent['id'], str(value.get('id') or ''), str(value.get('state') or '')[:40])
            elif kind == 'ping':
                await session.send_json({'type': 'pong'})
    finally:
        with _lock:
            if SESSIONS.get(agent['id']) is session:
                SESSIONS.pop(agent['id'], None)
            for job in JOBS.values():
                if job['agent'] == agent['id'] and job['status'] == 'running':
                    job.update(status='failed', result={'error': 'L’agente si è scollegato prima di rispondere'})
        for writer in list(session.streams.values()):
            writer.close()
        agents.seen(agent['id'])
        agents.log(agent['user'], agent['id'], 'disconnected', agent.get('name', ''))


async def _bridge(identifier, target, reader, writer):
    """One client of a tunnel listener (a worker opening the serial port or device) ↔ one agent stream."""
    with _lock:
        session = SESSIONS.get(identifier)
    if session is None:
        writer.close()
        return
    stream = session.next_stream
    session.next_stream += 1
    opened = asyncio.Event()
    session.opened[stream] = opened
    session.streams[stream] = writer
    await session.send_json({'type': 'open', 'stream': stream, 'target': target})
    try:
        await asyncio.wait_for(opened.wait(), 20)
    except asyncio.TimeoutError:
        session.streams.pop(stream, None)
        writer.close()
        return
    if stream not in session.streams:  # the agent refused
        writer.close()
        return
    agents.log(session.agent['user'], identifier, 'tunnel', target)
    with _lock:
        ACTIVE[(identifier, target)] = ACTIVE.get((identifier, target), 0) + 1
    try:
        while True:
            data = await reader.read(32768)
            if not data:
                break
            await session.send_bytes(stream, data)
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        with _lock:
            left = ACTIVE.get((identifier, target), 1) - 1
            if left > 0:
                ACTIVE[(identifier, target)] = left
            else:
                ACTIVE.pop((identifier, target), None)
        if session.streams.pop(stream, None) is not None:
            try:
                await session.send_json({'type': 'close', 'stream': stream})
            except Exception:
                pass
        writer.close()


def in_use(identifier, prefix):
    """Whether a tool holds a tunnel of this agent whose target starts with prefix (a Bluetooth device: one client at a time)."""
    with _lock:
        return any(agent == identifier and target.startswith(prefix) for agent, target in ACTIVE)


def address():
    """Where the server's workers reach the gateway's tunnels."""
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return '127.0.0.1'


def tunnel(identifier, target):
    """A TCP port of the gateway that carries one target of an agent (opened on demand, kept while the server runs)."""
    with _lock:
        if (identifier, target) in TUNNELS:
            return address(), TUNNELS[(identifier, target)][1]
        if identifier not in SESSIONS or LOOP is None:
            raise ValueError('L’agente non è collegato: avvia RigHaven Agent sul PC')
        used = {port for _, port in TUNNELS.values()}

    async def start():
        for port in TUNNEL_PORTS:
            if port in used:
                continue
            try:
                server = await asyncio.start_server(lambda r, w: _bridge(identifier, target, r, w), '0.0.0.0', port)
                return server, port
            except OSError:
                continue
        raise ValueError('Nessuna porta libera per il tunnel')

    server, port = asyncio.run_coroutine_threadsafe(start(), LOOP).result(timeout=15)
    with _lock:
        TUNNELS[(identifier, target)] = (server, port)
    return address(), port
