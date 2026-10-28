"""Gateway-owned output transactions. Workers can write only their own staging tree.

Canonical paths stay stable for native projects. No staging path is published as
an accepted project artifact. Promotion is append-only, after container removal.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import threading

from .progress import JOB_ID, workspace_key, read_status, utcnow
from .state import atomic_json

MAX_FILES = 100000
MAX_BYTES = 16 * 1024**3


def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Staging non valido')
    found = {}; size = 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(folder) / name
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                raise ValueError('Link o file speciale nello staging: ' + str(path.relative_to(root)))
            if stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    raise ValueError('Hard link nello staging')
                size += info.st_size
                if size > MAX_BYTES or len(found) >= MAX_FILES:
                    raise ValueError('Staging superiore al limite di pubblicazione')
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                found[str(path.relative_to(root))] = {'size': info.st_size, 'sha256': digest}
    return found


class TaskStaging:
    def __init__(self, state, workspace, agent, job_id):
        if not JOB_ID.fullmatch(job_id) or not agent or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in agent):
            raise ValueError('Identità staging non valida')
        self.workspace = Path(workspace).resolve()
        self.relative = Path('outputs') / agent / job_id
        self.logical = PurePosixPath('/mnt/user-data') / self.relative
        self.directory = Path(state) / 'task-staging' / workspace_key(self.workspace) / job_id
        self.output = self.directory / 'output'
        self.destination = self.workspace / self.relative
        self.receipt = self.directory / 'transaction.json'

    def prepare(self):
        self.output.mkdir(parents=True, exist_ok=False, mode=0o755)
        for path in (self.destination.parent, self.destination):
            if path.is_symlink() or not path.resolve().is_relative_to(self.workspace):
                raise ValueError('Destinazione incarico non valida')
        # Docker needs the nested bind target to exist inside a read-only mount.
        self.destination.mkdir(parents=True, exist_ok=False, mode=0o755)
        self.record('staging')

    def record(self, status, **fields):
        atomic_json(self.receipt, {'version': 1, 'status': status, 'job_id': self.logical.name,
            'workspace_key': workspace_key(self.workspace), 'output_dir': str(self.logical), 'at': utcnow(), **fields})

    def mounts(self, mount, progress):
        return ['--mount', mount(self.workspace, '/mnt/user-data', True),
                '--mount', mount(self.workspace, '/workspace/project', True),
                '--mount', mount(self.output, str(self.logical)),
                '--mount', mount(Path(progress).parent, '/mnt/user-data/.righaven-jobs/' + self.logical.name),
                '--env', 'RIGHAVEN_ISOLATED_OUTPUT=1']

    def validate(self, result, root=None):
        from .handoff import validate_delivery
        root = Path(root or self.output)
        files = inventory(root)
        def document(name, maximum):
            if name not in files or files[name]['size'] > maximum:
                raise ValueError('Contratto di output mancante o troppo grande: ' + name)
            value = json.loads((root / name).read_text())
            if not isinstance(value, dict):
                raise ValueError('Contratto di output non valido')
            return value
        handoff = document('handoff.json', 100000)
        delivery = document('delivery-manifest.json', 2000000)
        if (result.get('ok') is not True or result.get('output_dir') != str(self.logical)
                or delivery.get('id') != self.logical.name or delivery != result.get('delivery_record')):
            raise ValueError('Risposta diversa dal contratto di output salvato')
        if not isinstance(handoff.get('task'), str) or not handoff['task'].strip():
            raise ValueError('Contratto di output senza incarico')
        validate_delivery(handoff)
        for field in ('output_files', 'previews', 'source_files'):
            names = handoff.get(field)
            if not isinstance(names, list) or field == 'output_files' and not names:
                raise ValueError('Contratto di output incompleto')
            for name in names:
                path = PurePosixPath(name)
                if '..' in path.parts or not path.is_absolute():
                    raise ValueError('Percorso di consegna non valido')
                if path.is_relative_to(self.logical):
                    entry = files.get(str(path.relative_to(self.logical)))
                    if not entry or field != 'source_files' and not entry['size']:
                        raise ValueError('File dichiarato mancante o vuoto')
                elif field == 'source_files' and path.is_relative_to('/mnt/user-data'):
                    source = self.workspace / path.relative_to('/mnt/user-data')
                    if not source.resolve().is_relative_to(self.workspace) or not source.is_file():
                        raise ValueError('Input dichiarato non disponibile')
                else:
                    raise ValueError('Output fuori dallo staging dell’incarico')
        records = delivery.get('files', [])
        if not records or {f.get('path') for f in records} != {f['path'] for f in handoff['delivery']['files']}:
            raise ValueError('Inventario della consegna incompleto')
        for item in records:
            path = PurePosixPath(item['path'])
            if not path.is_relative_to(self.logical):
                raise ValueError('Consegna fuori dallo staging')
            actual = files.get(str(path.relative_to(self.logical)))
            if not actual or any(item.get(k) != actual[k] for k in ('sha256', 'size')):
                raise ValueError('File cambiato dopo la verifica nativa')
        return files

    def publish(self, result):
        receipt = json.loads(self.receipt.read_text()) if self.receipt.exists() else {}
        if receipt.get('status') == 'published':
            files = self.validate(result, self.destination)
            if files != receipt.get('files'):
                raise ValueError('Consegna pubblicata modificata: non sovrascrivo')
            result['output_transaction'] = {'status':'published','job_id':self.logical.name,'files_count':len(files)}
            return result
        files = self.validate(result)
        # Copy the entire tree, including frames/media, relative references and
        # command evidence. An empty reserved destination is never a delivery.
        temporary = self.destination.with_name('.' + self.destination.name + '-publish')
        if temporary.exists():
            shutil.rmtree(temporary)
        self.record('validating', files=files)
        try:
            shutil.copytree(self.output, temporary)
            if inventory(temporary) != files:
                raise ValueError('Copia dello staging non integra')
            if self.destination.is_symlink():
                raise ValueError('Destinazione già occupata: nessuna sovrascrittura consentita')
            if self.destination.exists() and any(self.destination.iterdir()):
                if inventory(self.destination) != files:
                    raise ValueError('Destinazione già occupata: nessuna sovrascrittura consentita')
                # Crash after rename, before receipt: commit is idempotent.
            else:
                os.replace(temporary, self.destination)
            self.record('published', files=files)
            try:
                shutil.rmtree(self.output)  # Do not keep a second copy of successful renders.
            except OSError:
                pass  # Publication succeeded; housekeeping must not undo its outcome.
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        result['output_transaction'] = {'status': 'published', 'job_id': self.logical.name, 'files_count': len(files)}
        return result

    def quarantine(self):
        if self.receipt.exists() and json.loads(self.receipt.read_text()).get('status') == 'published':
            return
        self.record('quarantined')
        if self.destination.is_dir() and not self.destination.is_symlink() and not any(self.destination.iterdir()):
            self.destination.rmdir()


@contextmanager
def forward_worker_events(workspace, progress):
    """Only current-job telemetry is writable; Gateway owns the chat journal."""
    import sqlite3
    from .audit_log import append, page
    stop = threading.Event(); last = 0
    def forward():
        nonlocal last
        try:
            while True:
                events = page(Path(progress).parent, after=last, limit=200)['events']
                if not events: return
                for event in events:
                    if not append(workspace, event['actor'], event['operation'], event['status'],
                        detail=event['detail'], correlation=event['correlation'], identifier=event['id'],
                        at=event['at'], context=event.get('context')):
                        return  # Retry the same rows after a transient journal error.
                    last = event['seq']
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            pass
    def loop():
        while not stop.wait(.25): forward()
    thread = threading.Thread(target=loop, daemon=True); thread.start()
    try: yield
    finally:
        stop.set(); thread.join(timeout=2); forward()


def open_job_file(state, workspace, filename):
    """Owned diagnostics during staging and after publication, without symlink races."""
    path = PurePosixPath(filename)
    parts = path.parts
    if (len(parts) < 7 or parts[:4] != ('/', 'mnt', 'user-data', 'outputs')
            or '..' in parts or not JOB_ID.fullmatch(parts[5])):
        raise ValueError('Percorso incarico non valido')
    from .progress import job_path
    status = read_status(job_path(workspace, parts[5]))
    if status.get('workspace_key') != workspace_key(workspace) or status.get('agent') != parts[4]:
        raise ValueError('Incarico estraneo alla conversazione')
    stage = TaskStaging(state, workspace, parts[4], parts[5])
    staged = stage.output.exists()
    root = stage.output if staged else stage.workspace
    components = list(parts[6:]) if staged else [*stage.relative.parts, *parts[6:]]
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in components[:-1]:
            if stat.S_ISLNK(os.lstat(part, dir_fd=fd).st_mode):
                raise OSError('Symlink parent not allowed')
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        if stat.S_ISLNK(os.lstat(components[-1], dir_fd=fd).st_mode):
            raise OSError('Symlink file not allowed')
        result = os.open(components[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        info = os.fstat(result)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_BYTES:
            os.close(result)
            raise ValueError('File diagnostico non valido')
        return os.fdopen(result, 'rb')
    finally:
        os.close(fd)
