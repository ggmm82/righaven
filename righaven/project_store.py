"""Project file storage: locking, validated loading and safe paths inside the conversation."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import uuid

from .progress import JOB_ID, job_path, read_status, update, utcnow, workspace_key
from .work_results import partial_files
from .state import atomic_json


STEP_ID = re.compile(r'[a-z][a-z0-9_-]{0,47}\Z')


PROJECT_ID = re.compile(r'[0-9a-f]{32}\Z')


MAX_HISTORY = 20


GATEWAY_SESSION = uuid.uuid4().hex


@contextmanager
def locked(workspace):
    root = Path(workspace).resolve()
    folder = root / '.righaven-project'
    if folder.is_symlink() or not folder.resolve().is_relative_to(root):
        raise ValueError('Percorso progetto non valido')
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(folder / 'project.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield folder
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def load(folder, workspace):
    path = folder / 'project.json'
    if not path.exists():
        return None
    if path.is_symlink() or path.stat().st_size > 1000000:
        raise ValueError('Stato progetto non valido')
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not isinstance(value.get('id'), str) or not PROJECT_ID.fullmatch(value['id']):
        raise ValueError('Identificatore progetto non valido')
    steps = value.get('steps')
    if not isinstance(steps, list) or not 0 <= len(steps) <= 64:
        raise ValueError('Fasi del progetto non valide')
    for step in steps:
        if (not isinstance(step, dict) or not isinstance(step.get('id'), str)
                or not STEP_ID.fullmatch(step['id']) or not isinstance(step.get('agent'), str)
                or not isinstance(step.get('goal'), str) or not isinstance(step.get('depends_on'), list)
                or not isinstance(step.get('attempts'), list) or len(step['attempts']) > 100
                or any(not isinstance(a, dict) for a in step['attempts'])
                or step.get('status') not in ('pending', 'running', 'completed', 'needs_revision', 'review', 'paused', 'skipped')
                or (step['status'] in ('running', 'completed') and not step['attempts'])):
            raise ValueError('Stato della fase non valido')
    if value.get('workspace_key') != workspace_key(workspace):
        return None
    from .revisions import number_attempts
    changed = number_attempts(value)
    if value.get('project_type') == 'animated_video' and 'requirements' not in value:
        value['requirements'] = {'video': True, 'audio': not bool(value.get('omissions', {}).get('soundcraft'))}
        changed = True
    for step in steps:
        if step['status'] == 'running' and step['attempts'][-1].get('gateway_session') != GATEWAY_SESSION:
            step['status'] = 'paused'
            step['attempts'][-1].update(status='paused', finished_at=utcnow(),
                error='Gateway riavviato: ispeziona i file persistenti e riprendi questa fase')
            job_id = Path(step['attempts'][-1].get('output_dir', '')).name
            if JOB_ID.fullmatch(job_id):
                try:
                    progress = job_path(workspace, job_id)
                    saved = read_status(progress)
                    if saved.get('workspace_key') == workspace_key(workspace) and saved['phase'] not in ('completed', 'failed', 'timed_out'):
                        update(progress, 'failed', 'Incarico fermato dal riavvio; i file salvati sono recuperabili')
                except (OSError, ValueError):
                    pass
            changed = True
    if changed:
        value['updated_at'] = utcnow()
        atomic_json(path, value)
    return value


def workspace_path(workspace, filename, worker_root=Path('/mnt/user-data')):
    root = Path(workspace).resolve()
    path = Path(str(filename))
    # A physical workspace may itself live below /mnt/user-data (native tests
    # and some installations). Prefer an already-scoped path before translating
    # the worker's virtual root, otherwise the conversation prefix is doubled.
    if not path.is_relative_to(root) and path.is_relative_to(worker_root):
        path = root / path.relative_to(worker_root)
    if not path.is_absolute() or not path.resolve().is_relative_to(root):
        return None
    return path


def artifact_path(workspace, filename):
    path = workspace_path(workspace, filename)
    if path is None:
        return None
    if not path.is_file() or path.is_symlink() or not path.stat().st_size:
        return None
    return path


def public_artifact(workspace, filename):
    path = artifact_path(workspace, filename)
    return '/mnt/user-data/' + path.relative_to(Path(workspace).resolve()).as_posix() if path else None


def available_paths(workspace, attempt):
    paths = attempt.get('output_files', [])
    if paths or not workspace or not attempt.get('output_dir'):
        return paths
    folder = workspace_path(workspace, attempt['output_dir'])
    if folder is None:
        return []
    return partial_files(folder)
