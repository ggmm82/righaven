"""DeepSeek is used through the OpenAI-compatible connection: migrate older installations.

The former DeepSeek engine stored only an API key and always called https://api.deepseek.com.
Each such key becomes an OpenAI-compatible connection to the same endpoint; profiles,
specialist overrides and hosted organization profiles follow it, and the old key is removed.
"""
import json
import os
from pathlib import Path
import tempfile
import uuid

import yaml

DEEPSEEK_URL = 'https://api.deepseek.com'
OLD_PROVIDER = 'righaven.deepseek_provider:HarnessDeepSeekChatModel'
NEW_PROVIDER = 'righaven.openai_provider:HarnessCompatibleChatModel'


def _write(path, value, text=None):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.migrate-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text if text is not None else json.dumps(value))
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _connection(key, connection_id):
    return {'api_key': key, 'base_url': DEEPSEEK_URL, 'connection_id': connection_id,
            'token_limit_param': 'max_tokens', 'tool_choice': 'specified', 'reasoning': False, 'vision': False}


def migrate_installation(base):
    """Shared (non-hosted) configuration under STATE."""
    config = base / 'config.yaml'
    old_key = base / 'credentials' / '.deepseek' / 'api.json'
    content = yaml.safe_load(config.read_text()) if config.is_file() else {}
    profiles = [m for m in (content or {}).get('models', []) if m.get('use') == OLD_PROVIDER]
    agents_path = base / 'agents.json'
    agents = json.loads(agents_path.read_text()) if agents_path.is_file() else {}
    overrides = [name for name, value in agents.items() if isinstance(value, dict) and value.get('engine') == 'deepseek']
    if not profiles and not overrides and not old_key.exists():
        return False
    connection_id = uuid.uuid4().hex
    folder = base / 'credentials' / '.openai'
    if old_key.is_file():
        key = json.loads(old_key.read_text()).get('api_key')
        if key:
            _write(folder / (connection_id + '.json'), _connection(key, connection_id))
            if not (folder / 'api.json').exists():
                _write(folder / 'api.json', _connection(key, connection_id))
    for profile in profiles:
        # Without a stored key the profile shows as not connected until it is configured again.
        profile.update(use=NEW_PROVIDER, connection_id=connection_id)
    if profiles:
        _write(config, None, yaml.safe_dump(content, allow_unicode=True, sort_keys=False))
    for name in overrides:
        # A specialist override follows the team profile, which now uses the migrated connection.
        agents[name].update(engine='inherit', model='')
    if overrides:
        _write(agents_path, agents)
    old_key.unlink(missing_ok=True)
    return True


def migrate_organization(directory, cipher):
    """Hosted profiles of one organization (encrypted credentials)."""
    models = directory / 'models.json'
    old_key = directory / 'credentials' / '.deepseek' / 'api.json'
    profiles = json.loads(models.read_text()) if models.is_file() else {}
    targets = [name for name, value in profiles.items() if isinstance(value, dict) and value.get('engine') == 'deepseek']
    if not targets and not old_key.exists():
        return False
    connection_id = uuid.uuid4().hex
    if old_key.is_file():
        stored = json.loads(old_key.read_text())
        secret = json.loads(cipher.decrypt(stored['encrypted'].encode()).decode()) if stored.get('format') == 'fernet:v2' else stored
        if secret.get('api_key'):
            value = {'api_key': secret['api_key'], 'base_url': DEEPSEEK_URL, 'connection_id': connection_id}
            _write(directory / 'credentials' / '.openai' / (connection_id + '.json'),
                   {'format': 'fernet:v2', 'encrypted': cipher.encrypt(json.dumps(value).encode()).decode()})
    for name in targets:
        profiles[name] = {**profiles[name], 'engine': 'openai', 'connection_id': connection_id}
    if targets:
        _write(models, profiles)
    old_key.unlink(missing_ok=True)
    return True


def migrate(base, cipher):
    changed = migrate_installation(base)
    for directory in sorted((base / 'organizations').glob('*')) if (base / 'organizations').is_dir() else []:
        changed = migrate_organization(directory, cipher) or changed
    return changed
