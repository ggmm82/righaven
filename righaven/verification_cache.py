"""Gateway-owned archive proofs, sent only through the read-only job descriptor."""
import json
from pathlib import Path
from .acceptance import fingerprint
from .source_packages import digest
from .progress import workspace_key
from .state import atomic_json


def scope(root, workspace, runtime):
    from .runtime_bundle import sources
    import hashlib
    code = hashlib.sha256()
    for section, name, source in sources():
        code.update((section + '/' + name).encode() + b'\0' + source.read_bytes() + b'\0')
    policy = fingerprint({'worker_bundle': code.hexdigest(), 'runtime': runtime, 'verifier': digest(Path(__file__).with_name('source_packages.py')),
                          'tools': digest(Path(__file__).with_name('versions.lock.json'))})
    return Path(root) / 'verification-cache' / workspace_key(workspace) / policy


def load(root, workspace, runtime):
    folder = scope(root, workspace, runtime)
    result = {}
    if folder.is_symlink():
        return result
    for path in sorted(folder.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:12]:
        if not path.is_symlink() and path.stat().st_size <= 500000:
            try:
                value = json.loads(path.read_text())
                if value.get('status') == 'passed' and value.get('sha256') == path.stem:
                    result[path.stem] = value
            except (ValueError, OSError):
                pass
    return result


def save(root, workspace, runtime, result):
    from .projects import artifact_path
    folder = scope(root, workspace, runtime)
    for item in (result.get('delivery_record') or {}).get('files', []):
        proof = item.get('verification') or {}
        if item.get('role') != 'source_archive' or proof.get('status') != 'passed':
            continue
        path = artifact_path(workspace, item.get('path', ''))
        if not path or proof.get('sha256') != digest(path):
            continue
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_json(folder / (proof['sha256'] + '.json'), proof)
