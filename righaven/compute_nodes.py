"""On-premise environments: sandboxes run on a dedicated machine of the owner, coordinated from here.

Coordination, projects, data and approvals stay on this server. A compute node is an agent whose
machine has Docker and that declares what it offers (CPU, memory, how many tasks at a time). When
an environment runs on premise, the worker's ``docker run`` is the same as here: this server
packs the folders it mounts (project, output, progress, credentials, connections, skills) into a
bundle; the node downloads bundle and image, checks the command against its sandbox rules, runs
it, sends the progress back while it runs and the results at the end; publication, validation and
audit then continue here as for a local worker.
"""
import json
import math
import os
import re
import shutil
import subprocess
import tarfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from . import agent_hub, agents

PLACES = ('cloud', 'auto')
JOB_NAME = re.compile(r'rh-job-[0-9a-f]{12}\Z')
MOUNT = re.compile(r'type=bind,src=([^,]+),dst=([^,]+)(,readonly)?\Z')
MAX_BUNDLE = 8 << 30
MAX_RESULT = 8 << 30

_lock = threading.Condition()
LEASES = {}  # node id → {job name: resources}
RUNS = {}    # job name → Run


class Run:
    def __init__(self, name, node, mounts, folder):
        self.name, self.node, self.mounts, self.folder = name, node, mounts, folder
        self.state, self.result, self.done = 'sent', None, threading.Event()
        self.image = ''
        # The job's progress file as the node last had it: only what the node changed since is
        # taken, so the server's own writes (a stop request, the limits) are never undone.
        self.seen = {}


def folder():
    from .state import STATE
    path = STATE / 'compute-runs'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


# --- Nodes and placement ---------------------------------------------------------------

def capacity(node):
    return agent_hub.state(node).get('compute')


def listing(user):
    """The owner's compute nodes, connected or not, with what they offer and run now."""
    rows = []
    for row in agents.listing(user):
        offered = capacity(row['id'])
        with _lock:
            running = sorted(LEASES.get(row['id'], {}))
        if offered or running:
            rows.append({'id': row['id'], 'name': row['name'], 'online': agent_hub.online(row['id']), 'compute': offered, 'running': running})
    return rows


def check_place(user, place):
    """An environment's place: cloud (this server), auto, or one of the owner's agents."""
    place = str(place or 'cloud')
    if place in PLACES:
        return place
    agents.owned(user, place)
    return place


def choose(user, profile, records, *, egress='open'):
    """Where a task of this environment runs: None for this server, or the ID of a compute node.

    An explicit node is used or refused with the reason; *auto* takes the node next to the
    task's on-premise connections, otherwise the connected node with most free CPU, otherwise
    this server.
    """
    if not user or not profile:
        return None
    from .environments import preferences
    place = preferences(user).get(profile, {}).get('placement') or 'cloud'
    if place == 'cloud':
        return None
    through = {r['agent'] for r in records if r.get('agent') and not (r['kind'] == 'device' and r.get('transport') == 'bluetooth')}
    blockers = _blockers(records, egress)
    if place != 'auto':
        name = agents.owned(user, place).get('name', place)
        if not capacity(place):
            raise ValueError('Questa macchina non esegue ambienti (avvia RigHaven Agent con «agent node on» oppure scegli Cloud): ' + name)
        problem = blockers or ([f'connessioni tramite un altro PC ({", ".join(sorted(through - {place}))})'] if through - {place} else [])
        if problem:
            raise ValueError(f'Questo incarico non può essere eseguito su «{name}»: ' + '; '.join(problem) + '. Scegli Cloud per questo ambiente')
        return place
    if blockers or len(through) > 1:
        return None
    nodes = [r for r in agents.listing(user) if capacity(r['id'])]
    if through:
        node = next(iter(through))
        return node if any(r['id'] == node for r in nodes) else None
    if not nodes:
        return None
    return max(nodes, key=lambda r: free(r['id'])[0])['id']


def _blockers(records, egress):
    problems = []
    if egress == 'allowlist':
        problems.append('l’uscita di rete limitata (allowlist) vale solo per questo server')
    for record in records:
        if record['kind'] == 'device' and record.get('transport') == 'local':
            problems.append(f'il dispositivo {record["id"]} è collegato a questo server')
        elif record['kind'] == 'device' and record.get('agent') and record.get('transport') == 'serial':
            problems.append(f'la porta COM di {record["id"]} passa da un tunnel di questo server')
        elif not record.get('agent') and record['kind'] not in ('entra', 'network') and _private(record):
            problems.append(f'la connessione {record["id"]} è nella rete di questo server')
    return problems


def _private(record):
    from .connections import location
    return location(record)[0] == 'on_premise'


# --- Resources of each node ------------------------------------------------------------

def free(node):
    offered = capacity(node) or {}
    with _lock:
        used = list(LEASES.get(node, {}).values())
    return (offered.get('cpus', 0) - sum(v['cpus'] for v in used), offered.get('memory_mib', 0) - sum(v['memory_mib'] for v in used))


def share(offered):
    """One task's part of a node: the node's limits divided by the tasks it accepts at a time."""
    jobs = offered['jobs']
    cpus = math.floor(offered['cpus'] / jobs * 1000) / 1000
    memory = offered['memory_mib'] // jobs
    return {'cpus': cpus, 'memory_mib': memory, 'tmp_mib': min(1024, max(32, memory // 4)), 'threads': max(1, math.ceil(cpus)),
            'max_workers': jobs}


def acquire(node, owner, *, cancel=None, timeout=None, exact=None):
    """Wait for a free place on the node; the job keeps it until release."""
    deadline = None if timeout is None else time.monotonic() + timeout
    with _lock:
        while True:
            if cancel is not None and cancel.is_set():
                raise RuntimeError('Attesa risorse annullata')
            offered = capacity(node)
            leases = LEASES.setdefault(node, {})
            if owner in leases:
                return leases[owner]
            if offered and len(leases) < offered['jobs']:
                value = {**share(offered), **(exact or {}), 'node': node}
                leases[owner] = value
                return value
            if deadline is not None and time.monotonic() >= deadline:
                raise RuntimeError('La macchina on premise è occupata o scollegata')
            _lock.wait(.5)


def release(owner):
    with _lock:
        for leases in LEASES.values():
            leases.pop(owner, None)
        _lock.notify_all()


# --- Remote runs -----------------------------------------------------------------------

def prepare(node, args, live):
    """The docker-run arguments with every bind source replaced by a bundle key, and the bundle."""
    from .docker_runtime import gateway_path
    if not args or args[0] != 'run' or '--name' not in args:
        raise ValueError('Comando del worker non valido')
    name = args[args.index('--name') + 1]
    if not JOB_NAME.fullmatch(name):
        raise ValueError('Nome del worker non valido')
    template, mounts, i = [], [], 0
    while i < len(args):
        item = args[i]
        if item in ('--device', '-v', '--volume', '--privileged') or item.startswith(('--device=', '--cap-add', '--network=')) and item != '--network=bridge':
            raise ValueError('Questo incarico usa risorse di questo server (' + item.split('=')[0] + '): eseguilo in cloud')
        if item == '--mount':
            matched = MOUNT.fullmatch(args[i + 1])
            if not matched:
                raise ValueError('Volume del worker non supportato su una macchina on premise')
            source = Path(gateway_path(matched.group(1)))
            key = 'm' + str(len(mounts))
            mode = 'ro' if matched.group(3) else ('live' if live and source == Path(live) else 'rw')
            mounts.append({'key': key, 'mode': mode, 'kind': 'dir' if source.is_dir() else 'file', 'source': str(source), 'target': matched.group(2)})
            template += ['--mount', f'type=bind,src={{{key}}},dst={matched.group(2)}' + (',readonly' if matched.group(3) else '')]
            i += 2
            continue
        template.append(item)
        i += 1
    run = Run(name, node, mounts, folder() / name)
    for mount in mounts:
        status = Path(mount['source']) / 'progress.json'
        if mount['mode'] == 'live' and status.is_file():
            try:
                run.seen[mount['key']] = json.loads(status.read_text())
            except ValueError:
                pass
    if run.folder.exists():
        shutil.rmtree(run.folder)
    run.folder.mkdir(mode=0o700)
    _pack(run.folder / 'bundle.tar.gz', mounts, ('ro', 'rw', 'live'), limit=MAX_BUNDLE)
    return run, template


def _pack(target, mounts, modes, limit):
    size = 0
    def keep(info):
        nonlocal size
        if info.issym() or info.islnk() or not (info.isfile() or info.isdir()):
            return None  # links and special files never leave this server
        size += info.size
        if size > limit:
            raise ValueError('Dati dell’incarico troppo grandi per una macchina on premise')
        info.uid = info.gid = 0
        info.uname = info.gname = ''
        return info
    with tarfile.open(target, 'w:gz') as archive:
        for mount in mounts:
            if mount['mode'] in modes and Path(mount['source']).exists():
                archive.add(mount['source'], arcname=mount['key'], filter=keep)


def run(node, args, *, timeout, live=None):
    """Run the worker's docker command on the node; the answer looks like subprocess.run's."""
    run_, template = prepare(node, args, live)
    image = _image(template)
    run_.image = image
    with _lock:
        RUNS[run_.name] = run_
    try:
        agent_hub.send(node, {'type': 'run', 'id': run_.name, 'args': template, 'image': image, 'timeout': int(timeout),
                              'mounts': [{k: m[k] for k in ('key', 'mode', 'kind', 'target')} for m in run_.mounts]})
        owner = agent_hub.owner(node)
        agents.log(owner, node, 'compute-run', run_.name, 'asked')
        # The node keeps its results while it is offline and sends them when it comes back.
        if not run_.done.wait(timeout + 120):
            stop(run_.name)
            raise subprocess.TimeoutExpired(['docker', *args], timeout)
        result = run_.result
        agents.log(owner, node, 'compute-run', f'{run_.name} · exit {result["returncode"]}', 'done' if not result['returncode'] else 'failed')
        return SimpleNamespace(returncode=result['returncode'], stdout=result.get('stdout', ''), stderr=result.get('stderr', ''),
                               oom=bool(result.get('oom')))
    finally:
        with _lock:
            RUNS.pop(run_.name, None)
        shutil.rmtree(run_.folder, ignore_errors=True)


def _image(template):
    i = 1
    while i < len(template):
        item = template[i]
        if item in ('--name', '--label', '--tmpfs', '--env', '--mount', '--pids-limit'):
            i += 2
        elif item.startswith('-'):
            i += 1
        else:
            return item
    raise ValueError('Immagine del worker mancante')


def get(node, name):
    with _lock:
        value = RUNS.get(name)
    if value is None or value.node != node:
        raise LookupError(name)
    return value


def started(node, name, state):
    try:
        get(node, name).state = state
    except LookupError:
        pass


def stop(name):
    with _lock:
        value = RUNS.get(name)
    if value is not None:
        try:
            agent_hub.send(value.node, {'type': 'stop', 'id': name})
        except ValueError:
            pass
        return True
    return False


def _unpack(stream, run_, modes):
    """Files sent back by the node, only into the folders it was given to write."""
    targets = {m['key']: m for m in run_.mounts if m['mode'] in modes}
    with tarfile.open(fileobj=stream, mode='r:*') as archive:
        members = []
        for member in archive.getmembers():
            key = member.name.split('/', 1)[0]
            if member.name == 'result.json':
                continue
            if key not in targets or not (member.isfile() or member.isdir()) or '..' in Path(member.name).parts or member.name.startswith('/'):
                continue
            members.append(member)
        for member in members:
            mount = targets[member.name.split('/', 1)[0]]
            relative = member.name.split('/', 1)[1] if '/' in member.name else ''
            destination = Path(mount['source']) / relative if mount['kind'] == 'dir' else Path(mount['source'])
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if mount['kind'] == 'file' and relative:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if mount['mode'] == 'live' and relative == 'progress.json':
                _merge_progress(run_, mount, destination, archive.extractfile(member).read())
                continue
            temporary = destination.with_name('.' + destination.name + '.node')
            with archive.extractfile(member) as source, open(temporary, 'wb') as target:
                shutil.copyfileobj(source, target)
            os.replace(temporary, destination)  # readers never see half a file
        try:
            outcome = json.load(archive.extractfile('result.json'))
        except (KeyError, ValueError, AttributeError):
            outcome = None
    return outcome


def _merge_progress(run_, mount, destination, data):
    from .progress import edit_status
    try:
        sent = json.loads(data)
    except ValueError:
        return
    if not isinstance(sent, dict):
        return
    before = run_.seen.get(mount['key'], {})
    with edit_status(destination) as value:
        for key, item in sent.items():
            if key != 'node' and before.get(key) != item:
                value[key] = item
    run_.seen[mount['key']] = sent


def receive_live(node, name, stream):
    _unpack(stream, get(node, name), ('live',))


def receive_result(node, name, stream):
    run_ = get(node, name)
    outcome = _unpack(stream, run_, ('rw', 'live'))
    if not isinstance(outcome, dict) or type(outcome.get('returncode')) is not int:
        raise ValueError('Risultato della macchina on premise non valido')
    run_.result = {'returncode': outcome['returncode'], 'stdout': str(outcome.get('stdout') or '')[:16 << 20],
                   'stderr': str(outcome.get('stderr') or '')[:1 << 20], 'oom': outcome.get('oom') is True}
    run_.done.set()


def bundle(node, name):
    return get(node, name).folder / 'bundle.tar.gz'


def image_for(node, image):
    """An environment image a node may download: only one of a run sent to that node."""
    with _lock:
        allowed = any(r.node == node and r.image == image for r in RUNS.values())
    if not allowed:
        raise LookupError(image)
    return image


def last_result(name):
    with _lock:
        value = RUNS.get(name)
    return value.result if value else None


def placement_label(user, place):
    if place in (None, '', 'cloud'):
        return 'cloud'
    if place == 'auto':
        return 'auto'
    try:
        return agents.owned(user, place).get('name', place)
    except ValueError:
        return place

