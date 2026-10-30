"""Reuse an owner's prepared profile as the base of an assignment environment.

A role brings its skills and the tools they require. Among the owner's
preloaded, ready profiles the runtime prefers the one containing most of the
role's skills, then most of its tools, and adopts that profile's versions for
the covered tools, so the image is reused as is or extended with only the
missing tools. Outcomes are structured codes; the interface words them in the
viewer's language.
"""
import hashlib
import json
import time

from . import state

CRITERIA = ('skills', 'tools', 'missing', 'extra', 'size')


def _usage_path(user, name):
    key = hashlib.sha256((str(user) + '\0' + name).encode()).hexdigest()
    return state.STATE / 'environment-usage' / (key + '.json')


def usage(user, name):
    path = _usage_path(user, name)
    if not path.exists() or path.is_symlink() or path.stat().st_size > 32000:
        return {'jobs': 0}
    return json.loads(path.read_text())


def record_use(user, name, role, mode):
    with state.LOCK:
        value = usage(user, name)
        value.update(jobs=value.get('jobs', 0) + 1, last_job_at=time.time(), last_role=str(role or '')[:140], last_mode=mode)
        state.atomic_json(_usage_path(user, name), value)


def profiles(user, policy):
    """Owner profiles kept ready: name, prepared image, authorized tools and active skills."""
    from .environment_preparation import read as preparation
    from . import environment_runtime as runtime
    try:
        from righaven_core.config.agents_config import list_custom_agents
        from .environments import preferences, profile
        prefs, agents = preferences(user), list_custom_agents(user_id=user)
    except (ImportError, OSError, ValueError):
        return  # Without owner profiles the assignment is prepared on its own.
    for agent in agents:
        if prefs.get(agent.name, {}).get('mode') != 'preload':
            continue
        try:
            record = runtime.read(preparation(user, agent.name).get('ready_id') or '')
            skills = set(profile(user, agent)['active_skills'])
        except (ValueError, OSError):
            continue
        if record and record.get('status') == 'ready' and runtime.image_exists(record):
            yield agent.name, record, set(record.get('tools', [])) & set(policy.get('allowed', [])), skills


def choose(user, needed, policy, skills=()):
    """Best ready profile for this role, or None when no profile shares a skill or a tool."""
    if not user or not (needed or skills):
        return None
    from .environment_runtime import closure
    wanted, wanted_skills = set(closure(needed)), set(skills) - {'skill-harness', 'skill-workspace'}
    best = None
    for name, record, tools, profile_skills in profiles(user, policy):
        covered, shared = wanted & tools, wanted_skills & profile_skills
        if not covered and not shared:
            continue
        score = (len(shared), len(covered), -len(wanted - covered), -len(tools - wanted), -record.get('size_bytes', 0))
        if best is None or score > best[0]:
            best = (score, name, record, covered, shared)
    if best is None:
        return None
    _, name, record, covered, shared = best
    return {'name': name, 'id': record['id'], 'covered': sorted(covered), 'missing': sorted(wanted - covered),
            'skills': sorted(shared), 'role_skills': sorted(wanted_skills), 'wanted': len(wanted),
            'versions': {t: r for t, r in record.get('versions', {}).items() if t in covered and not t.startswith('provider-')}}


def versions(chosen, base):
    """Adopt the profile's versions for the tools it covers, so its image matches."""
    if not base:
        return chosen
    return {**{t: r for t, r in chosen.items() if t not in base['covered']}, **base['versions']}


def outcome(base, environment):
    """How the assignment environment relates to the selected profile (codes, not prose)."""
    if not base:
        return {'mode': 'none'}
    if environment.get('id') == base['id']:
        mode, added = 'reused', []
    elif environment.get('base_environment_id') == base['id']:
        mode, added = 'extended', environment.get('install_tools') or base['missing']
    else:
        mode, added = 'not_reused', []
    return {'mode': mode, 'profile': base['name'], 'covered': base['covered'], 'missing': base['missing'],
            'added': added, 'skills': base['skills'], 'role_skills': base['role_skills'], 'wanted': base['wanted']}
