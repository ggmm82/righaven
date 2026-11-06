"""Owner-scoped configuration snapshots; never snapshots of a project's files."""
import hashlib
import json
import time
from . import environments, state


def path(user, name):
    if not environments.NAME.fullmatch(name):
        raise ValueError('Invalid environment name')
    return environments.preferences_path(user).parent / 'environment-history' / (name + '.json')


def read(user, name):
    target = path(user, name)
    return json.loads(target.read_text()) if target.is_file() else []


def record(user, profile):
    deployment = profile['deployment']
    definition = {key: profile.get(key, '') for key in ('name', 'display_name', 'purpose', 'instructions', 'skills')}
    definition.update({key: deployment.get(key, default) for key, default in (
        ('mode', 'on_demand'), ('ephemeral', False), ('preload_tools', None), ('tool_versions', {}))})
    digest = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    with state.LOCK:
        rows = read(user, profile['name'])
        if rows and rows[-1]['id'] == digest:
            return
        rows.append({'id': digest, 'saved_at': time.time(), 'definition': definition})
        state.atomic_json(path(user, profile['name']), rows[-50:])
