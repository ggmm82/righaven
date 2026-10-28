"""Release-specific code, mounted read-only over an immutable software environment.

The bundle contains trusted adapters only. Native skills are projected separately;
credentials and conversation files never participate in a software image/cache key.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from . import state


def sources():
    root = Path(os.getenv('RIGHAVEN_WORKER_SOURCE', Path(__file__).resolve().parents[1]))
    manifest = json.loads((root / 'config/worker-bundle.json').read_text())
    for section in ('righaven', 'righaven-worker'):
        for name, relative in sorted(manifest[section].items()):
            source = root / relative
            if (Path(name).name != name or source.is_symlink()
                    or not source.resolve().is_relative_to(root.resolve()) or not source.is_file()):
                raise ValueError('Pacchetto di esecuzione non valido')
            yield section, name, source


def stage():
    """Publish atomically by content hash; an active job keeps its previous bundle."""
    files = [(section, name, source.read_bytes()) for section, name, source in sources()]
    digest = hashlib.sha256()
    for section, name, data in files:
        digest.update((section + '/' + name).encode() + b'\0' + data + b'\0')
    revision = digest.hexdigest()
    parent = state.STATE / 'runtime-bundles'
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise ValueError('Directory di esecuzione non valida')
    destination = parent / revision
    # Recheck contents rather than trusting a persistent directory's name.
    if destination.exists():
        if destination.is_symlink():
            raise ValueError('Pacchetto di esecuzione non valido')
        expected = {section + '/' + name: data for section, name, data in files}
        actual = {}
        for path in destination.rglob('*'):
            if path.is_symlink():
                raise ValueError('Pacchetto di esecuzione alterato')
            if path.is_file():
                actual[str(path.relative_to(destination))] = path.read_bytes()
        if actual != expected:
            raise ValueError('Pacchetto di esecuzione alterato')
        return destination
    temporary = Path(tempfile.mkdtemp(prefix='.staging-', dir=parent))
    try:
        for section, name, data in files:
            target = temporary / section / name
            target.parent.mkdir(exist_ok=True)
            target.parent.chmod(0o755)
            target.write_bytes(data)
            target.chmod(0o755 if target.suffix == '.py' else 0o644)
        try:
            temporary.rename(destination)
        except OSError:
            if not destination.is_dir():
                raise
            # Another thread may have published exactly the same immutable bundle.
            return stage()
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def arguments(*, skills=False):
    from .docker_runtime import mount
    bundle = stage()
    args = ['--mount', mount(bundle / 'righaven-worker', '/opt/righaven-worker', True)]
    # Mount files individually: /opt/righaven also holds installed apps and manifests.
    for path in sorted((bundle / 'righaven').iterdir()):
        args += ['--mount', mount(path, '/opt/righaven/' + path.name, True)]
    if skills:
        directory = Path(os.getenv('RIGHAVEN_BUNDLED_SKILLS', Path(__file__).resolve().parents[1] / 'skills'))
        # Bundled legacy instructions are copied into the state volume as well.
        from .skill_composition import package_revision
        revision = package_revision(directory, require_skill=False)
        target = state.STATE / 'runtime-skills' / revision
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            temporary = Path(tempfile.mkdtemp(prefix='.staging-', dir=target.parent))
            try:
                shutil.copytree(directory, temporary, dirs_exist_ok=True)
                try:temporary.rename(target)
                except OSError:
                    if not target.is_dir():raise
            finally:
                if temporary.exists():shutil.rmtree(temporary)
        target.chmod(0o755)
        if target.is_symlink() or package_revision(target, require_skill=False) != revision:
            raise ValueError('Skill del rilascio alterate')
        args += ['--mount', mount(target, '/mnt/skills', True)]
    return args
