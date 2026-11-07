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
# When the chosen machine is offline: wait up to N minutes for it, or run the task in the cloud.
UNAVAILABLE = re.compile(r'(cloud|wait:([1-9][0-9]{0,2}))\Z')
DEFAULT_UNAVAILABLE = 'wait:15'
JOB_NAME = re.compile(r'rh-job-[0-9a-f]{12}\Z')
PREPARATION_NAME = re.compile(r'rh-env-[0-9a-f]{12}-[0-9a-f]{6}\Z')
ENVIRONMENT_TAG = re.compile(r'skill-environment:[0-9a-f]{12}-[0-9a-f]{64}\Z')
MOUNT = re.compile(r'type=bind,src=([^,]+),dst=([^,]+)(,readonly)?\Z')
MAX_BUNDLE = 8 << 30
MAX_PART = 16 << 20  # one part of a result sent in parts
ACK_TIMEOUT = 120  # seconds for a connected node to confirm it received a run
PREPARATION_EXTRA = 2 * 3600  # base image download and docker commit of a preparation, on top of its run
MAX_RESULT = 8 << 30

_lock = threading.Condition()
LEASES = {}  # node id → {job name: resources}
RUNS = {}    # job name → Run


class Run:
    def __init__(self, name, node, mounts, folder):
        self.name, self.node, self.mounts, self.folder = name, node, mounts, folder
        self.state, self.result, self.done = 'sent', None, threading.Event()
        self.image = ''
        self.preparation = None  # {'tag', 'environment'} when the run prepares an environment image
        self.on_state = None     # called with the node's states: image (downloading it), running
        self.on_output = None    # called with a preparation's output while it runs
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
    """The owner's PCs: those that run on-premise environments (compute) with what they offer and run
    now, and the others with why not, so the page can say what to do."""
    rows = []
    for row in agents.listing(user):
        offered = capacity(row['id'])
        with _lock:
            running = sorted(LEASES.get(row['id'], {}))
        online = agent_hub.online(row['id'])
        reason = '' if offered else ('offline' if not online else 'not_a_node')
        rows.append({'id': row['id'], 'name': row['name'], 'online': online, 'compute': offered, 'running': running,
                     'platform': row.get('platform', ''), 'reason': reason})
    return rows


def check_place(user, place):
    """An environment's place: cloud (this server), auto, or one of the owner's agents."""
    place = str(place or 'cloud')
    if place in PLACES:
        return place
    agents.owned(user, place)
    return place


def check_unavailable(value):
    value = str(value or DEFAULT_UNAVAILABLE)
    matched = UNAVAILABLE.fullmatch(value)
    if not matched or (matched.group(2) and int(matched.group(2)) > 240):
        raise ValueError('If the machine is offline: cloud, or wait 1-240 minutes')
    return value


def waiting_minutes(user, profile):
    """How long a task waits for its offline machine; None when it goes to the cloud instead."""
    from .environments import preferences
    value = (preferences(user).get(profile, {}) if user and profile else {}).get('unavailable') or DEFAULT_UNAVAILABLE
    return None if value == 'cloud' else int(value.split(':')[1])


def choose(user, profile, records, *, egress='open', notes=None):
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
        if not agent_hub.online(place):
            if waiting_minutes(user, profile) is None:
                if notes is not None:
                    notes.append(f'«{name}» è scollegato: l’incarico viene eseguito in cloud, come scelto per questo ambiente')
                return None
            # Waits for the machine (acquire), within the environment's limit.
        elif not capacity(place):
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


def runs_here(node, records, egress='open'):
    """Whether a task with these connections can run on this connected node (no server-bound resource)."""
    if not agent_hub.online(node) or not capacity(node) or _blockers(records, egress):
        return False
    through = {r['agent'] for r in records if r.get('agent') and not (r['kind'] == 'device' and r.get('transport') == 'bluetooth')}
    return not (through - {node})


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


def acquire(node, owner, *, cancel=None, timeout=None, exact=None, label=None, offline_timeout=None):
    """Wait for a free place on the node; the job keeps it until release.

    A busy node is a queue, as on the server: the task waits for its turn. offline_timeout bounds
    only the time the machine stays disconnected; timeout (tests, recovery) bounds the whole wait."""
    deadline = None if timeout is None else time.monotonic() + timeout
    offline_since = None
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
            now = time.monotonic()
            if agent_hub.online(node):
                offline_since = None
            elif offline_since is None:
                offline_since = now
            if offline_timeout is not None and offline_since is not None and now - offline_since >= offline_timeout:
                minutes = max(1, round(offline_timeout / 60))
                raise RuntimeError(f'La macchina «{label or node}» è scollegata e non è tornata entro {minutes} minuti: avvia RigHaven Agent sulla macchina, '
                                   'oppure scegli per questo ambiente di eseguire in cloud quando la macchina non c’è')
            if deadline is not None and now >= deadline:
                raise RuntimeError(f'La macchina «{label or node}» è occupata o scollegata: riprova più tardi')
            _lock.wait(.5)


def release(owner):
    with _lock:
        for leases in LEASES.values():
            leases.pop(owner, None)
        _lock.notify_all()


# --- Remote runs -----------------------------------------------------------------------

def prepare(node, args, live, preparation=False):
    """The docker-run arguments with every bind source replaced by a bundle key, and the bundle.

    A preparation (an environment image built on the node) may add only the capabilities the
    package installers need, as on this server; a task may add none."""
    from .docker_runtime import gateway_path
    from .environment_runtime import PREPARATION_CAPABILITIES
    if not args or args[0] != 'run' or '--name' not in args:
        raise ValueError('Comando del worker non valido')
    name = args[args.index('--name') + 1]
    if not (PREPARATION_NAME if preparation else JOB_NAME).fullmatch(name):
        raise ValueError('Nome del worker non valido')
    template, mounts, i = [], [], 0
    while i < len(args):
        item = args[i]
        if preparation and item == '--cap-add' and i + 1 < len(args) and args[i + 1] in PREPARATION_CAPABILITIES:
            template += args[i:i + 2]
            i += 2
            continue
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


def run(node, args, *, timeout, live=None, preparation=None, on_state=None, on_output=None):
    """Run the worker's docker command on the node; the answer looks like subprocess.run's.

    With preparation={'tag', 'environment'} the node saves the container as that environment
    image (docker commit) when the command succeeds, and answers with its image_id and size."""
    run_, template = prepare(node, args, live, preparation=preparation is not None)
    image = _image(template)
    if image.startswith('sha256:'):
        # Docker image IDs differ between image stores (Docker Desktop's containerd store gives
        # the same image another ID): a node receives this server's images by name.
        named = portable_image(image)
        template[template.index(image)] = named
        image = named
    run_.image = image
    run_.preparation = preparation
    run_.on_state = on_state
    run_.on_output = on_output
    with _lock:
        RUNS[run_.name] = run_
    try:
        message = {'type': 'run', 'id': run_.name, 'args': template, 'image': image, 'timeout': int(timeout),
                   'mounts': [{k: m[k] for k in ('key', 'mode', 'kind', 'target')} for m in run_.mounts]}
        if preparation is not None:
            message['prepare'] = {'tag': preparation['tag'], 'environment': preparation['environment']}
        agent_hub.send(node, message)
        owner = agent_hub.owner(node)
        agents.log(owner, node, 'compute-run', run_.name, 'asked')
        # A node confirms each run at once; one that does not (an agent too old to read it) would
        # otherwise leave the task waiting for its whole timeout.
        acknowledged = time.monotonic() + min(ACK_TIMEOUT, timeout + 120)
        while not run_.done.is_set() and run_.state == 'sent' and time.monotonic() < acknowledged:
            run_.done.wait(.5)
        if not run_.done.is_set() and run_.state == 'sent' and agent_hub.online(node):
            stop(run_.name)
            raise RuntimeError('La macchina on premise non ha preso in carico il lavoro: aggiorna RigHaven Agent sulla macchina '
                               'alla versione di questo server e riprova')
        # The node keeps its results while it is offline and sends them when it comes back. A
        # preparation also downloads the base image first and saves a large image at the end.
        if not run_.done.wait(timeout + 120 + (PREPARATION_EXTRA if preparation is not None else 0)):
            stop(run_.name)
            raise subprocess.TimeoutExpired(['docker', *args], timeout)
        result = run_.result
        agents.log(owner, node, 'compute-run', f'{run_.name} · exit {result["returncode"]}', 'done' if not result['returncode'] else 'failed')
        return SimpleNamespace(returncode=result['returncode'], stdout=result.get('stdout', ''), stderr=result.get('stderr', ''),
                               oom=bool(result.get('oom')), image_id=result.get('image_id', ''), size_bytes=result.get('size_bytes', 0))
    finally:
        with _lock:
            RUNS.pop(run_.name, None)
        shutil.rmtree(run_.folder, ignore_errors=True)


def portable_image(image):
    """A name for one of this server's images, kept by docker save and load on any image store."""
    tag = 'righaven-node:' + image.removeprefix('sha256:')[:32]
    try:
        subprocess.run(['docker', 'tag', image, tag], check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError('Immagine non disponibile su questo server per la macchina on premise') from error
    return tag


def _image(template):
    i = 1
    while i < len(template):
        item = template[i]
        if item in ('--name', '--label', '--tmpfs', '--env', '--mount', '--pids-limit', '--cap-add'):
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
        run_ = get(node, name)
    except LookupError:
        return
    run_.state = state
    if run_.on_state is not None:
        try:
            run_.on_state(state)
        except Exception:  # a progress display never stops the run
            pass


def output(node, name, text):
    try:
        run_ = get(node, name)
    except LookupError:
        return
    if run_.on_output is not None and text:
        try:
            run_.on_output(text)
        except Exception:  # a progress display never stops the run
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
    if run_.preparation is not None and not outcome['returncode']:
        image_id, size = outcome.get('image_id'), outcome.get('size_bytes')
        if not (isinstance(image_id, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', image_id)) or type(size) is not int or size < 0:
            raise ValueError('Immagine preparata dalla macchina on premise non valida')
        run_.result.update(image_id=image_id, size_bytes=size)
    run_.done.set()


class PartOutOfOrder(ValueError):
    def __init__(self, expected):
        super().__init__(f'part {expected} expected')
        self.expected = expected


def receive_part(node, name, part, data, final):
    """One part of a large result, appended in order; the last one completes it."""
    run_ = get(node, name)
    path = run_.folder / 'result.parts'
    with _lock:
        expected = getattr(run_, 'parts', 0)
        if part != expected:
            if part < expected:  # already here (an answer lost on the way): fine
                return False
            raise PartOutOfOrder(expected)
        if part == 0 and path.exists():
            path.unlink()
        size = path.stat().st_size if path.exists() else 0
        if size + len(data) > MAX_RESULT:
            raise ValueError('Risultato troppo grande')
        with path.open('ab') as stream:
            stream.write(data)
        run_.parts = part + 1
    if not final:
        return False
    try:
        with path.open('rb') as stream:
            receive_result(node, name, stream)
    finally:
        path.unlink(missing_ok=True)
    return True


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




# --- Environment images prepared on the node ----------------------------------------------
# A machine on premise prepares and keeps its own environment images: nothing is built or cached
# on this server for it, and its images are reused only by its own tasks. This server's cache is
# reused only in the cloud: the two never mix.

def _environments_file():
    from .state import STATE
    return STATE / 'compute-environments.json'


def _environments():
    path = _environments_file()
    try:
        value = json.loads(path.read_text()) if path.is_file() and not path.is_symlink() else {}
    except (OSError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def _save_environment(node, record):
    from .state import atomic_json
    with _lock:
        value = _environments()
        records = value.setdefault(node, {})
        records[record['id']] = record
        atomic_json(_environments_file(), value)


def node_images(node):
    """The environment images the node says it has now (it removes the least used ones itself)."""
    offered = capacity(node) or {}
    return set(offered.get('images') or ())


def prepares_environments(node):
    """Whether the node prepares environments itself (RigHaven Agent that reports its images)."""
    offered = capacity(node) or {}
    return isinstance(offered.get('images'), list)


def environments(node):
    """The node's ready environments whose image it still has (as last known while it is offline:
    nothing is prepared or run there until it is back and says what it has)."""
    records = [r for r in _environments().get(node, {}).values() if isinstance(r, dict) and r.get('status') == 'ready']
    if not prepares_environments(node):
        return records
    present = node_images(node)
    return [r for r in records if r.get('image_id') in present]


NODE_PHASES = {'image': '«{where}» scarica l’immagine base di RigHaven (la prima volta, alcuni GB)',
               'running': 'Preparo gli strumenti su «{where}»', 'installing': 'Installazione dei programmi su «{where}»',
               'adapters': 'Configurazione degli strumenti su «{where}»', 'checking': 'Collaudo dell’ambiente su «{where}»',
               'publishing': 'Salvataggio dell’immagine su «{where}»'}


def log_path(node, key):
    """The preparation log of an environment on a node, kept here for the Environments page."""
    from .state import STATE
    if not re.fullmatch(r'[0-9a-f]{64}', key) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', node):
        raise ValueError('Identità ambiente non valida')
    folder_ = STATE / 'compute-environment-logs'
    folder_.mkdir(parents=True, exist_ok=True, mode=0o700)
    return folder_ / f'{node}-{key}.log'


def preparation_text(node, key, *, since=None):
    path = log_path(node, key)
    if not path.is_file() or (since is not None and path.stat().st_mtime < since):
        return ''
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 12000))
        return stream.read(12000).decode('utf-8', errors='replace')


def preparation_observation(node, key, phase, *, since=None):
    """What the Environments page shows while a node prepares: the phase and the node's last output."""
    from .progress import clean_summary
    now, last, size, recent = time.time(), None, 0, ''
    path = log_path(node, key)
    if path.is_file() and (since is None or path.stat().st_mtime >= since):
        stat = path.stat()
        last, size = stat.st_mtime, stat.st_size
        tail = preparation_text(node, key)[-4096:]
        recent = next((clean_summary(line, 300) for line in reversed(tail.splitlines()) if line.strip()), '')
    return {'environment_id': key, 'phase': phase, 'tools': [], 'last_output_at': last, 'log_bytes': size,
            'recent_output': recent, 'observed_at': now, 'prerequisite': False}


def available(node, tools, identity=None, *, versions=None):
    """The environment the node would use now for these tools: one of its images, or on_demand."""
    from . import environment_runtime as env
    key, spec = env.recipe(tools, identity=identity, versions=versions)
    if not spec['tools'] and not spec.get('versions'):
        return {'id': key, 'status': 'ready', 'tools': [], 'core': True, 'node': node}
    records = environments(node)
    present = {r['id'] for r in records}
    ready = env.candidates(spec, records=records, exists=lambda item: item.get('id') in present)
    if ready:
        return ready[0]
    return {'id': key, 'status': 'on_demand', 'tools': spec['tools'], 'core': spec['core'], 'node': node,
            **({'software_abi': spec['software_abi']} if spec.get('software_abi') else {})}


def prepare_environment(node, owner, tools, *, versions=None, resources, progress=None, label=None, prefer=None, timeout=3600, report=None):
    """The environment of a task on premise: one of the node's images when it fits, otherwise
    prepared on the node, starting from the closest of its own images."""
    from . import environment_runtime as env
    from .docker_runtime import IMAGE
    key, spec = env.recipe(tools, versions=versions)
    if not spec['tools'] and not spec.get('versions'):
        return {'id': key, 'image': IMAGE, 'tools': [], 'status': 'ready', 'core': True}
    records = environments(node)
    present = {r['id'] for r in records}
    exists = lambda item: item.get('id') in present
    ready = env.candidates(spec, records=records, exists=exists, prefer=prefer)
    if ready:
        chosen = {**ready[0], 'last_used': time.time()}
        _save_environment(node, chosen)
        return chosen
    base = env.subset(spec, prefer, records=records, exists=exists)
    reused = env.reused_tools(base, spec)
    # The machine's own images by their name there; the core image is sent by this server.
    base_image = base['image'] if base else spec['core']
    name = 'rh-env-' + key[:12] + '-' + os.urandom(3).hex()
    work = folder() / (name + '-request')
    work.mkdir(mode=0o755)
    try:
        descriptor = env.write_descriptor(work / 'environment-request.json', spec, base, reused)
        args = env.preparation_arguments(name, resources, key, base_image, descriptor, progress)
        tag = env.image_tag(key)
        if progress:
            from .progress import update
            update(progress, 'preparing_environment', f'Preparo gli strumenti su «{label or node}»' +
                   (f' partendo da un suo ambiente ({", ".join(reused)} già pronti)' if reused else ''))
            update(progress, environment_container=name)  # a stop request reaches the node's container
        where = label or node

        log = log_path(node, key)
        log.write_text('')

        def on_output(text):
            with log.open('a') as stream:
                if log.stat().st_size < 4_000_000:
                    stream.write(text)
            for line in text.splitlines():  # the installer's phases, as on this server
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get('phase') in ('installing', 'adapters', 'checking', 'publishing'):
                    on_state(event['phase'])

        def on_state(state):
            if state.startswith('image:'):  # megabytes of the base image downloaded so far
                megabytes = state.split(':', 1)[1]
                if report is not None and megabytes.isdigit():
                    report('downloading_image', f'{megabytes} MB scaricati')
                if progress and megabytes.isdigit():
                    from .progress import update
                    update(progress, 'preparing_environment', f'«{where}» scarica l’immagine base: {megabytes} MB')
                return
            if report is not None:
                report({'image': 'downloading_image', 'running': 'preparing_machine'}.get(state, state))
            if progress and state in NODE_PHASES:
                from .progress import update
                update(progress, 'preparing_environment', NODE_PHASES[state].format(where=where))
        completed = run(node, args, timeout=timeout, preparation={'tag': tag, 'environment': key}, on_state=on_state, on_output=on_output)
        if progress:
            from .progress import read_status
            if read_status(progress).get('cancel_requested'):
                raise RuntimeError('Preparazione annullata')
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or '').strip().splitlines()[-1:] or ['']
        if completed.oom:
            raise RuntimeError(f'Memoria insufficiente su «{label or node}» durante la preparazione dell’ambiente')
        raise RuntimeError(f'Preparazione dell’ambiente su «{label or node}» non riuscita: ' + detail[0][:300])
    from .tool_versions import packages
    record = {'id': key, 'status': 'ready', 'image': tag, 'image_id': completed.image_id, 'size_bytes': completed.size_bytes,
              'tools': spec['tools'], 'core': spec['core'], 'software_abi': spec.get('software_abi'),
              'tool_fingerprints': spec.get('tool_fingerprints'), 'versions': spec.get('versions', {}),
              'version_names': {k: v['app']['version'] for k, v in packages(spec.get('versions', {})).items()},
              'installed_versions': env.verified_versions(completed.stdout), 'base_environment_id': (base or {}).get('id'),
              'reused_tools': reused, 'node': node, 'created_at': time.time(), 'last_used': time.time()}
    _save_environment(node, record)
    agent_hub.note_image(node, completed.image_id)  # until the node's next report
    return record
