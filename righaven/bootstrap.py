"""Initialize persistent configuration before the Gateway imports RigHaven."""
import hashlib
import json
import os
import secrets
import uuid
import re
from pathlib import Path

import yaml

from .state import STATE, ROOT, catalog


def configure_team(engine, model, api_key=None, *, scope='both', base_url=None, connection_id=None, token_limit_param='max_tokens', tool_choice='specified', reasoning=False, vision=False):
    """Apply a profile to coordinator, production workers, or both in one catalog."""
    from .state import LOCK, atomic_json, credential_dir, custom_connection_path, applications
    if engine not in ('codex', 'deepseek', 'gemini', 'openai') or scope not in ('both', 'coordinator', 'squad'):
        raise ValueError('Servizio o destinazione non disponibile')
    if tool_choice not in ('specified', 'required', 'auto'):
        raise ValueError('Modalità tool_choice non supportata')
    if not model or len(model) > 200 or any(ord(c) < 32 for c in model):
        raise ValueError('Modello non valido')
    if engine != 'openai' and not re.fullmatch(r'[a-z0-9][a-z0-9._:/-]*', model):
        raise ValueError('Usa l’identificatore del modello dall’elenco, non il nome visualizzato')
    with LOCK:
        path = STATE / 'config.yaml'
        content = yaml.safe_load(path.read_text())
        old = content.get('models', [])
        worker = next((p for p in old if p.get('name') == 'rh-squad'), None) or next(iter(old), {})
        entry = {'name': 'rh-codex', 'display_name': 'RigHaven Harness',
                 'use': {'deepseek': 'righaven.deepseek_provider:HarnessDeepSeekChatModel',
                         'codex': 'righaven.codex_provider:HarnessCodexChatModel',
                         'gemini': 'righaven.gemini_provider:HarnessGeminiChatModel',
                         'openai': 'righaven.openai_provider:HarnessCompatibleChatModel'}[engine],
                 'model': model, 'supports_thinking': engine == 'codex',
                 'supports_reasoning_effort': engine == 'codex', 'request_timeout': 1800}
        if engine == 'openai':
            if not connection_id:
                connection_id = uuid.uuid4().hex
            custom_connection_path(connection_id)  # Validate the opaque selector before writes.
            if not api_key or not base_url:
                raise ValueError('Endpoint e chiave API sono necessari per il collegamento personalizzato')
            entry['connection_id'] = connection_id
        if scope == 'squad':
            content['models'] = [p for p in old if p.get('name') != 'rh-squad'] + [{**entry, 'name': 'rh-squad', 'display_name': 'RigHaven Specialists'}]
        else:
            aliases = [{**entry, 'name': item['name']} for item in old if item['name'] == 'rh-deepseek']
            content['models'] = [entry, *aliases, *[m for m in old if m['name'] not in ('rh-codex', 'rh-deepseek', 'rh-squad')]]
            if scope == 'coordinator':
                content['models'].append({**worker, 'name': 'rh-squad', 'display_name': 'RigHaven Specialists'})
        split = any(p.get('name') == 'rh-squad' for p in content['models'])
        for identifier, definition in content.get('subagents', {}).get('custom_agents', {}).items():
            if identifier in {a['id'] for a in applications()}:
                definition['model'] = 'rh-squad' if split else 'inherit'
        temporary = path.with_suffix('.yaml.tmp')
        try:
            temporary.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=False))
            temporary.chmod(0o600)
            if engine == 'deepseek' and api_key is not None:
                atomic_json(credential_dir('deepseek') / 'api.json', {'api_key': api_key})
            elif engine == 'openai':
                credentials = {'api_key': api_key, 'base_url': base_url, 'connection_id': connection_id, 'token_limit_param': token_limit_param, 'tool_choice': tool_choice, 'reasoning': bool(reasoning), 'vision': bool(vision)}
                atomic_json(custom_connection_path(connection_id), credentials)
                atomic_json(custom_connection_path(), credentials)
            if scope in ('both', 'squad'):
                agents = catalog()
                for settings in agents.values():
                    settings.update(engine='inherit', model='')
                atomic_json(STATE / 'agents.json', agents)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def configure_coordinator(model):
    from .state import team, custom_connection_path
    profile = team()
    if profile['engine'] == 'openai':
        connection = json.loads(custom_connection_path(profile.get('connection_id')).read_text())
        configure_team('openai', model, connection['api_key'], base_url=connection['base_url'], connection_id=connection['connection_id'], token_limit_param=connection.get('token_limit_param','max_tokens'))
    else:
        configure_team(profile['engine'], model)


def configure_deepseek(api_key, model):
    configure_team('deepseek', model, api_key)


def initialize():
    STATE.mkdir(parents=True, exist_ok=True)
    password = os.getenv('RIGHAVEN_PASSWORD', '')
    if len(password) < 16:
        raise ValueError('RIGHAVEN_PASSWORD deve contenere almeno 16 caratteri')
    identifier = STATE / 'installation-id'
    if not identifier.exists():
        identifier.write_text(uuid.uuid4().hex)
    key = STATE / 'credentials-key'
    if not os.getenv('RIGHAVEN_CREDENTIALS_KEY') and not key.exists():
        import base64
        key.write_text(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        key.chmod(0o600)
    if not os.getenv('RIGHAVEN_CREDENTIALS_KEY'):
        os.environ['RIGHAVEN_CREDENTIALS_KEY'] = key.read_text().strip()
    from .tenant_profiles import cipher
    cipher()  # Validate the standard encryption keys before starting the service.
    os.environ['BETTER_AUTH_SECRET'] = hashlib.sha256(password.encode()).hexdigest()
    path = STATE / 'config.yaml'
    if not path.exists():
        path.write_text((ROOT / 'righaven.yaml').read_text())
        path.chmod(0o600)
    else:
        # Migrate installations created before the Codex wire-compatibility
        # provider was introduced, without replacing user-selected models.
        content = yaml.safe_load(path.read_text())
        changed = False
        for item in content.get('models', []):
            if item.get('name') == 'rh-codex' and item.get('use') == 'righaven_core.models.openai_codex_provider:CodexChatModel':
                item['use'] = 'righaven.codex_provider:HarnessCodexChatModel'
                changed = True
        template = yaml.safe_load((ROOT / 'righaven.yaml').read_text())
        for tool in template.get('tools', []):
            if tool.get('name') in ('harness_plan', 'harness_lessons', 'harness_read_context','harness_skills','harness_delegate_batch') and not any(
                    t.get('name') == tool.get('name') for t in content.get('tools', [])):
                content.setdefault('tools', []).append(tool)
                changed = True
        definitions = content.setdefault('subagents', {}).setdefault('custom_agents', {})
        for identifier, definition in template['subagents']['custom_agents'].items():
            if identifier not in definitions:
                definitions[identifier] = definition
                changed = True
        inherited_model = 'rh-squad' if any(p.get('name') == 'rh-squad' for p in content.get('models', [])) else 'inherit'
        for identifier in template['subagents']['custom_agents']:
            if definitions[identifier].get('model') != inherited_model:
                definitions[identifier]['model'] = inherited_model
                changed = True
        if content.get('agents_api') != {'enabled': True}:
            content['agents_api'] = {'enabled': True}
            changed = True
        if content.get('skills', {}).get('path') == '/app/skills':
            content['skills']['path'] = '/app/skill-catalog'
            changed = True
        overlay = content.get('lead_prompt_overlay', {})
        if overlay.get('append', '').startswith(('Per ogni lavoro RigHaven usa harness_delegate', 'Sei la RigHaven Harness.')):
            if overlay['append'] != template['lead_prompt_overlay']['append']:
                overlay['append'] = template['lead_prompt_overlay']['append']
                changed = True
        if any(t.get('name') == 'harness_delegate' for t in content.get('tools', [])):
            # Coordinator writes could turn a binary export into a text placeholder.
            # The specialists own product creation; retain custom unrelated tools.
            previous = content['tools']
            content['tools'] = [t for t in previous if not (
                t.get('name') in ('write_file', 'str_replace')
                and t.get('use', '').startswith('righaven_core.sandbox.tools:'))]
            if previous != content['tools']:
                changed = True
                if not any(t.get('group') == 'file:write' for t in content['tools']):
                    content['tool_groups'] = [g for g in content.get('tool_groups', []) if g.get('name') != 'file:write']
        if changed:
            temporary = path.with_suffix('.yaml.tmp')
            temporary.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=False))
            temporary.chmod(0o600)
            temporary.replace(path)
    migration = STATE / 'google-provider-antigravity-v1'
    if not migration.exists():
        # Old Gemini API model IDs do not identify Antigravity subscription models.
        content = yaml.safe_load(path.read_text())
        changed = False
        for profile in content.get('models', []):
            if profile.get('use') == 'righaven.gemini_provider:HarnessGeminiChatModel':
                profile['model'] = 'auto'
                changed = True
        if changed:
            temporary = path.with_suffix('.yaml.tmp')
            temporary.write_text(yaml.safe_dump(content, allow_unicode=True, sort_keys=False))
            temporary.chmod(0o600)
            temporary.replace(path)
        agents = catalog()
        for settings in agents.values():
            if settings['engine'] == 'gemini':
                settings.update(engine='inherit', model='')
        from .state import atomic_json
        atomic_json(STATE / 'agents.json', agents)
        migration.write_text('Official agy account login required; legacy tokens retained but unused.\n')
    extension = STATE / 'extensions_config.json'
    if not extension.exists():
        extension.write_text((ROOT / 'extensions_config.json').read_text())
    from .state import atomic_json
    extensions = json.loads(extension.read_text())
    configured = extensions.setdefault('middlewares', [])
    for middleware in ('righaven.audit_middleware:ConversationAuditMiddleware',
                       'righaven.completion_middleware:ProjectCompletionMiddleware'):
        if middleware not in configured:
            configured.append(middleware)
            atomic_json(extension, extensions)
    from .persistent_database import configure as configure_database
    configure_database(path, STATE)
    catalog()


def main():
    initialize()
    from .capability_policy import install_managed_skills, migrate_existing_users
    install_managed_skills()
    migrate_existing_users()
    from .docker_runtime import cleanup_orphans
    cleanup_orphans()
    from .organization_limits import recover_after_cleanup
    recover_after_cleanup()
    # exec preserves signal delivery, while the env secrets stay in this process tree.
    os.execvp('uvicorn', ['uvicorn', 'righaven.app:app', '--host', '0.0.0.0',
                        '--port', '8001', '--workers', '1',
                        '--timeout-graceful-shutdown', '15'])


if __name__ == '__main__':
    main()
