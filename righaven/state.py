"""Small persistent configuration catalog. No credentials in public responses."""
import json
import os
import tempfile
import threading
from pathlib import Path

STATE = Path(os.getenv('RIGHAVEN_STATE', '/righaven-state'))
ROOT = Path(__file__).resolve().parent
LOCK = threading.RLock()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def applications():
    return json.loads((ROOT / 'versions.lock.json').read_text())['applications']


def default_skills(identifier):
    return ['skill-workspace', 'skill-' + identifier]


def available_skills():
    return ['skill-workspace', *['skill-' + a['id'] for a in applications()]]


def catalog():
    with LOCK:
        path = STATE / 'agents.json'
        if not path.exists():
            atomic_json(path, {app['id']: {'engine': 'inherit', 'model': '',
                        'instructions': '', 'enabled': True, 'skills': default_skills(app['id'])} for app in applications()})
        agents = json.loads(path.read_text())
        changed = False
        for app in applications():
            identifier = app['id']
            if identifier not in agents:
                agents[identifier] = {'engine': 'inherit', 'model': '', 'instructions': '',
                                     'enabled': True, 'skills': default_skills(identifier)}
                changed = True
        for identifier, config in agents.items():
            if 'skills' not in config:
                config['skills'] = default_skills(identifier)
                changed = True
        if changed:
            atomic_json(path, agents)
        return agents


def update_agent(identifier, value):
    if identifier not in {a['id'] for a in applications()}:
        raise ValueError('Specialista sconosciuto')
    if value['engine'] not in ('inherit', 'codex', 'gemini', 'deepseek', 'openai', 'claude'):
        raise ValueError('Motore sconosciuto')
    model = value.get('model', '').strip()
    if len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ValueError('Modello non valido')
    if len(value.get('instructions', '')) > 20000:
        raise ValueError('Istruzioni troppo lunghe')
    skills = value.get('skills') or default_skills(identifier)
    if not isinstance(skills, list) or not all(isinstance(s, str) and s in available_skills() for s in skills):
        raise ValueError('Skill sconosciuta')
    skills = list(dict.fromkeys(['skill-workspace', 'skill-' + identifier, *skills]))
    with LOCK:
        agents = catalog()
        agents[identifier] = {'engine': value['engine'], 'model': model,
                              'instructions': value.get('instructions', ''),
                              'enabled': bool(value.get('enabled', True)), 'skills': skills}
        atomic_json(STATE / 'agents.json', agents)
    return agents[identifier]


def credential_dir(engine):
    if engine not in ('codex', 'gemini', 'deepseek', 'openai', 'claude'):
        raise ValueError('Motore sconosciuto')
    from .tenant_profiles import root
    directory = (root() or STATE) / 'credentials' / ('.' + engine)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def connection_status(engine, connection_id=None):
    if engine == 'openai':
        return custom_connection_path(connection_id).is_file()
    if engine == 'gemini':
        return all((credential_dir(engine) / name).is_file() for name in (
            'antigravity-cli/antigravity-oauth-token', 'antigravity-account.json'))
    filename = {'codex': 'auth.json', 'deepseek': 'api.json','claude':'.credentials.json'}[engine]
    return (credential_dir(engine) / filename).is_file()


def custom_connection_path(connection_id=None):
    import re
    if connection_id is not None and not re.fullmatch(r'[0-9a-f]{32}', connection_id):
        raise ValueError('Collegamento OpenAI compatibile non valido')
    return credential_dir('openai') / ((connection_id or 'api') + '.json')


def team(target='coordinator'):
    """Two optional scopes in the same catalog; old installations remain shared."""
    import yaml
    from .tenant_profiles import profile
    hosted = profile(target)
    if hosted is not None:
        return {**hosted, 'ready': connection_status(hosted['engine'], hosted.get('connection_id'))}
    path = STATE / 'config.yaml'
    with LOCK:
        content = yaml.safe_load(path.read_text()) if path.exists() else {}
        profiles = content.get('models', [])
        profile = next((p for p in profiles if p.get('name') == 'rh-squad'), None) if target == 'squad' else None
        profile = profile or next(iter(profiles), {})
        engine = {'righaven.deepseek_provider:HarnessDeepSeekChatModel': 'deepseek',
                  'righaven.gemini_provider:HarnessGeminiChatModel': 'gemini',
                  'righaven.claude_provider:HarnessClaudeChatModel': 'claude',
                  'righaven.openai_provider:HarnessCompatibleChatModel': 'openai'}.get(profile.get('use'), 'codex')
        result = {'engine': engine, 'model': profile.get('model', 'gpt-6.1-sol'),
                  'ready': connection_status(engine, profile.get('connection_id'))}
        if engine == 'openai':
            connection = json.loads(custom_connection_path(profile.get('connection_id')).read_text()) if result['ready'] else {}
            result.update(connection_id=profile.get('connection_id'), base_url=connection.get('base_url', ''))
        return result


def effective_agent(identifier):
    if identifier == 'workspace':
        profile = team('squad')
        return {**{k: v for k, v in profile.items() if k != 'ready'}, 'enabled': True, 'instructions': '', 'skills': ['skill-workspace']}
    with LOCK:
        settings = catalog().get(identifier)
        if settings is None:
            return None
        settings = dict(settings)
        if settings['engine'] == 'inherit':
            profile = team('squad')
            settings.update({k: v for k, v in profile.items() if k != 'ready'})
        return settings
