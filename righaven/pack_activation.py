"""Activate reviewed packs through native skills and environment configuration."""
import hashlib
import tempfile
import zipfile
from pathlib import Path
import yaml


async def install(pack, user_id):
    from .state import applications
    from .environments import resolve_skills, set_deployment
    from righaven_core.skills.storage import get_or_new_user_skill_storage
    known = {item['id'] for item in applications()}
    tools = pack.get('tools', [])
    deps = pack.get('docker_dependencies', {})
    if any(deps.get(key) for key in ('system_packages', 'python_packages', 'node_packages', 'nix_packages')):
        raise ValueError('Direct package installation is not supported. Declare managed tools; their verified runtime recipes supply dependencies.')
    if set(tools) - known:
        raise ValueError('This pack requires tools not supported by the runtime catalog')
    names = list(dict.fromkeys([*pack.get('skills', []), *['skill-' + tool for tool in tools]]))
    scope = resolve_skills(user_id, names)
    if scope['disabled']:
        raise ValueError('Pack requires disabled skills: ' + ', '.join(scope['disabled']))
    identity = {key: pack[key] for key in ('id', 'version', 'tools', 'skill_prompt_template', 'category')}
    identity.update({key:pack[key] for key in ('skills','environment') if key in pack})
    digest = hashlib.sha256(__import__('json').dumps(identity, sort_keys=True).encode()).hexdigest()
    name = 'pack-' + pack['id'][:40] + '-' + digest[:12]
    storage = get_or_new_user_skill_storage(user_id)
    if pack['category'] == 'skill':
        if not storage.custom_skill_exists(name):
            metadata = {'name': name, 'description': pack['i18n']['en']['description'],
                        'metadata': {'righaven-tools': tools, 'pack-sha256': digest}}
            content = '---\n' + yaml.safe_dump(metadata) + '---\n' + pack['skill_prompt_template'] + '\n'
            with tempfile.TemporaryDirectory(prefix='righaven-pack-') as folder:
                archive = Path(folder) / 'pack.skill'
                with zipfile.ZipFile(archive, 'w') as output:
                    output.writestr(name + '/SKILL.md', content)
                await storage.ainstall_skill_from_archive(archive)
        storage.set_skill_enabled_state(name, True)
    elif pack['category'] == 'environment':
        from righaven_core.persistence.agents import get_agent_store
        from righaven_core.config.agents_config import load_agent_config
        try:
            existing = load_agent_config(name, user_id=user_id)
        except FileNotFoundError:
            existing = None
        if existing is None:
            get_agent_store().create(name, {'name': name, 'display_name': (pack.get('display_title') or pack['i18n']['en']['title'])[:64], 'description': pack.get('environment', {}).get('purpose') or pack['i18n']['en']['description'],
                                          'skills': ['skill-workspace', *names]},
                                     pack['skill_prompt_template'], user_id=user_id)
        if existing is None:
            set_deployment(user_id, name, 'on_demand', tool_versions=pack.get('environment', {}).get('tool_versions', {}))
    else:
        if not tools:
            raise ValueError('CLI packs must declare a supported tool')
    from righaven_core.agents.lead_agent.prompt import invalidate_user_skill_cache, publish_skills_cache_reset
    invalidate_user_skill_cache(user_id)
    publish_skills_cache_reset(user_id=user_id)
    return {'native_name': name, 'sha256': digest, 'tools': tools}
