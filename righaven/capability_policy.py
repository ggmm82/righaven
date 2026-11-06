"""Bridge native RigHaven skills/Agent scope to isolated RigHaven workers."""
from pathlib import Path
from .state import applications, catalog, atomic_json, LOCK


def install_managed_skills():
    """Register the bundled integration in RigHaven's managed provider layout."""
    import os
    import shutil
    import uuid
    from righaven_core.config.paths import get_paths
    source = Path('/app/skills/custom')
    parent = get_paths().integration_skills_dir()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / 'righaven'
    if target.is_symlink():
        raise ValueError('Installazione skills RigHaven non valida')
    staged = parent / ('.righaven-' + uuid.uuid4().hex)
    backup = parent / ('.righaven-backup-' + uuid.uuid4().hex)
    shutil.copytree(source, staged)
    if target.exists():
        target.rename(backup)
    try:
        os.replace(staged, target)
    except BaseException:
        if backup.exists():
            backup.rename(target)
        raise
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)


def current_policy():
    try:
        from righaven_core.runtime.user_context import get_effective_user_id
    except ModuleNotFoundError:
        import os
        if os.environ.get('RIGHAVEN_HOME'):
            raise
        return legacy_policy()  # Standalone configuration tools/tests only.
    return native_policy(get_effective_user_id())


def migrate_existing_users():
    """Import old global disables before the native Capability Center is served."""
    from righaven_core.config.paths import get_paths, _validate_user_id
    if not any(not config.get('enabled', True) for config in catalog().values()):
        return
    users = get_paths().base_dir / 'users'
    if users.is_dir():
        for directory in users.iterdir():
            if directory.is_dir() and not directory.is_symlink():
                try:
                    user_id = _validate_user_id(directory.name)
                except ValueError:
                    continue
                native_policy(user_id)


def legacy_policy():
    settings = catalog()
    return policy_from_names({'skill-' + a['id'] for a in applications()
                              if settings.get(a['id'], {}).get('enabled', False)}, source='legacy')


def policy_from_names(names, *, source='righaven_core'):
    known = {a['id'] for a in applications()}
    allowed = sorted(a for a in known if 'skill-' + a in names)
    return {'source': source, 'allowed': allowed, 'blocked': sorted(known - set(allowed))}


def native_policy(user_id, agent_name=None):
    from righaven_core.skills.storage import get_or_new_user_skill_storage
    from righaven_core.config.paths import get_paths
    from righaven_core.config.agents_config import load_agent_config
    storage = get_or_new_user_skill_storage(user_id)
    # One-time compatibility import; native user choices win when already saved.
    # The marker is migration bookkeeping, never a second enable/disable setting.
    root = get_paths().user_dir(user_id)
    marker = root / 'righaven-native-skills-migrated.json'
    if marker.is_symlink():
        raise ValueError('Migrazione skills non valida')
    with LOCK:
        if not marker.exists():
            state_path = root / 'skills/_skill_states.json'
            if state_path.is_symlink():
                raise ValueError('Stato skills non valido')
            import json
            saved = json.loads(state_path.read_text()) if state_path.exists() else {}
            migrated = []
            for identifier, config in catalog().items():
                name = 'skill-' + identifier
                if not config.get('enabled', True) and name not in saved:
                    storage.set_skill_enabled_state(name, False)
                    migrated.append(name)
            if migrated:
                from righaven_core.agents.lead_agent.prompt import invalidate_user_skill_cache, publish_skills_cache_reset
                invalidate_user_skill_cache(user_id)
                publish_skills_cache_reset(user_id=user_id)
            atomic_json(marker, {'version': 1, 'imported': migrated})
    found = storage.load_skills(enabled_only=True)
    names = {s.name for s in found}
    extra = []
    if agent_name:
        agent = load_agent_config(agent_name, user_id=user_id)
        if agent is None:
            raise ValueError('Agent nativo non trovato')
        if agent.skills is not None:
            names &= set(agent.skills)
            packaged_tools = {'skill-' + a['id'] for a in applications()}
            extra = sorted(names - packaged_tools - {'skill-workspace', 'skill-harness'})
    # Personal skill requirements extend this native scope only with enabled managed skills.
    from .environments import skill_requirements
    enabled_names = {s.name for s in found}
    for skill in found:
        if agent_name and agent.skills is not None and skill.name in names:
            for tool in skill_requirements(skill):
                dependency = 'skill-' + tool
                if dependency not in enabled_names:
                    raise ValueError('La skill '+skill.name+' richiede uno strumento disabilitato: '+tool)
                names.add(dependency)
    result = policy_from_names(names)
    result.update(user_id=user_id, agent_name=agent_name, skill_names=sorted(names), extra_skills=extra,
                  skill_sources={s.name: str(s.skill_dir) for s in found if s.name in names})
    return result


def runtime_policy(runtime):
    from righaven_core.runtime.user_context import resolve_runtime_user_id
    raw = getattr(runtime, 'config', None) or {}
    config = dict(raw.get('configurable') or {})
    config.update(raw.get('context') or {})
    context = getattr(runtime, 'context', None) or {}
    if isinstance(context, dict):
        config.update(context)
    inherited = raw.get('configurable') or {}
    agent_name = inherited['righaven_agent_name'] if 'righaven_agent_name' in inherited else config.get('agent_name')
    return native_policy(resolve_runtime_user_id(runtime), agent_name)


def public(policy):
    return {k: policy[k] for k in ('source', 'allowed', 'blocked')}


def require_tools(policy, tools):
    missing = sorted(set(tools) - set(policy['allowed']))
    if missing:
        raise ValueError('Strumento disabilitato o escluso dall’Agent: ' + ', '.join(missing) +
                         '. Ripianifica con le capacità native disponibili; workspace non autorizza un aggiramento.')


def worker_arguments(policy, blocker_host_path, *, projected_skills=False):
    """Mask bundled native apps and system entry points outside writable job data."""
    blocked = set(policy['blocked'])
    result = []
    for app in applications():
        if app['id'] not in blocked:
            continue
        result += ['--tmpfs', '/opt/righaven/apps/' + app['id'] + ':ro,size=1m']
        install = app.get('install', {})
        if install.get('kind') in ('debian','upstream-deb'):
            paths = list(dict.fromkeys([install['native_path'],*install.get('native_paths',[])]))
            for path in paths:
                result += ['--mount', 'type=bind,src=' + str(blocker_host_path) + ',dst=' + path + ',readonly']
        if app['id'] == 'ffmpeg':
            # Also mask distribution aliases if installed transitively. The
            # pinned source build and local symlinks are masked by apps/ffmpeg.
            for path in ('/usr/bin/ffmpeg', '/usr/bin/ffprobe'):
                result += ['--mount', 'type=bind,src=' + str(blocker_host_path) + ',dst=' + path + ',readonly']
        if app['id'] == 'playwright':
            paths=['/opt/righaven/toolkit']
            browser_users={a['id'] for a in applications() if a.get('install',{}).get('kind')=='design-node' or a.get('install',{}).get('uses_shared_browser')}
            if browser_users.issubset(blocked):paths.append('/opt/righaven/playwright-browsers')
            for path in paths:
                result += ['--tmpfs', path + ':ro,size=1m']
        if not projected_skills:
            result += ['--tmpfs', '/mnt/skills/custom/skill-' + app['id'] + ':ro,size=1m']
    return result


def stage_skills(policy, names, destination):
    """Project actual native packages, with references, into this read-only run."""
    import re
    import shutil
    destination = Path(destination)
    destination.mkdir(mode=0o700)
    total, count = 0, 0
    for name in names:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name) or name not in policy['skill_sources']:
            raise ValueError('Skill non autorizzata nel profilo nativo')
        source = Path(policy['skill_sources'][name]).resolve()
        if not (source / 'SKILL.md').is_file():
            raise ValueError('Pacchetto skill nativo non disponibile')
        for path in source.rglob('*'):
            if not path.resolve().is_relative_to(source):
                raise ValueError('Riferimento esterno nel pacchetto skill')
            target = destination / name / path.relative_to(source)
            if path.is_dir():
                if path.is_symlink():
                    raise ValueError('Usa directory reali per i riferimenti della skill')
                target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                total += path.stat().st_size
                count += 1
                if total > 32 * 1024 * 1024 or count > 2000:
                    raise ValueError('Skills troppo grandi per il contesto del worker')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            else:
                raise ValueError('File speciale nel pacchetto skill')
    return destination
