"""Reuse an owner's prepared profile as the base of an assignment environment.

A role composes its own tools. Among the owner's preloaded, ready profiles the
runtime picks the one covering most of them and adopts that profile's versions
for the covered tools, so its image is reused as is or extended with only the
missing tools. The choice and its reason are recorded on the assignment.
"""
import hashlib
import json
import time

from . import state

SCORE = 'programmi coperti, poi meno programmi mancanti, poi meno programmi in più, poi immagine più piccola'


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
    """Owner profiles kept ready, with the image they prepared."""
    from .environment_preparation import read as preparation
    from . import environment_runtime as runtime
    try:
        from righaven_core.config.agents_config import list_custom_agents
        from .environments import preferences
        prefs, agents = preferences(user), list_custom_agents(user_id=user)
    except (ImportError, OSError, ValueError):
        return  # Without owner profiles the assignment is prepared on its own.
    for agent in agents:
        if prefs.get(agent.name, {}).get('mode') != 'preload':
            continue
        try:
            record = runtime.read(preparation(user, agent.name).get('ready_id') or '')
        except (ValueError, OSError):
            continue
        if record and record.get('status') == 'ready' and runtime.image_exists(record):
            yield agent.name, record, set(record.get('tools', [])) & set(policy.get('allowed', []))


def choose(user, needed, policy):
    """Best ready profile for these tools, or None when no profile covers any of them."""
    if not user or not needed:
        return None
    from .environment_runtime import closure
    wanted = set(closure(needed))
    best = None
    for name, record, tools in profiles(user, policy):
        covered = wanted & tools
        if not covered:
            continue
        score = (len(covered), -len(wanted - covered), -len(tools - wanted), -record.get('size_bytes', 0))
        if best is None or score > best[0]:
            best = (score, name, record, covered)
    if best is None:
        return None
    _, name, record, covered = best
    missing = sorted(wanted - covered)
    return {'name': name, 'id': record['id'], 'covered': sorted(covered), 'missing': missing,
            'versions': {t: r for t, r in record.get('versions', {}).items() if t in covered and not t.startswith('provider-')},
            'reason': ('Il profilo ' + name + ' copre ' + str(len(covered)) + ' di ' + str(len(wanted)) + ' programmi richiesti'
                       + ('; mancano ' + ', '.join(missing) if missing else '') + '. Criterio: ' + SCORE + '.')}


def versions(chosen, base):
    """Adopt the profile's versions for the tools it covers, so its image matches."""
    if not base:
        return chosen
    return {**{t: r for t, r in chosen.items() if t not in base['covered']}, **base['versions']}


def outcome(base, environment):
    """How the assignment environment relates to the selected profile."""
    if not base:
        return {'mode': 'none', 'reason': 'Nessun profilo pronto copre i programmi di questo incarico: ambiente preparato su misura.'}
    if environment.get('id') == base['id']:
        mode, text = 'reused', 'Immagine del profilo riusata così com’è.'
    elif environment.get('base_environment_id') == base['id']:
        added = environment.get('install_tools') or base['missing']
        mode, text = 'extended', 'Immagine del profilo estesa con: ' + (', '.join(added) or 'nessun programma') + '.'
    else:
        mode, text = 'not_reused', ('Profilo non riusabile per questo incarico (versioni o installazione diverse): '
                                    'usato un altro ambiente compatibile.')
    return {'mode': mode, 'profile': base['name'], 'covered': base['covered'], 'missing': base['missing'],
            'reason': base['reason'] + ' ' + text}
