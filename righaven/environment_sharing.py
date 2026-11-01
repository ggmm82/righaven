"""Convert an owned environment into a portable, managed catalog manifest."""
from . import gallery, state


def manifest(profile, user, identifier, version, title_en, description_en, title_it, description_it):
    if profile.get('disabled'):
        raise ValueError('Remove or enable disabled skills before sharing')
    # Custom method files require a native skill package; references alone would lose them.
    known = {item['id'] for item in state.applications()}
    allowed = gallery.MANAGED_SKILLS | {'skill-' + item for item in known}
    if set(profile['skills']) - allowed:
        raise ValueError('Custom skill content cannot be shared by reference. Export its native skill package first.')
    instructions = profile.get('instructions') or profile['purpose']
    return gallery.validate_pack_manifest({
        'id': identifier, 'version': version, 'name': title_en, 'author': user, 'category': 'environment',
        'i18n': {'en': {'title': title_en, 'description': description_en}, 'it': {'title': title_it, 'description': description_it}},
        'tags': ['community', *profile['tools']], 'tools': profile['tools'],
        'skills': profile['skills'],
        'docker_dependencies': {'base_image': 'managed', 'system_packages': [], 'python_packages': [], 'node_packages': []},
        'cli_binaries': [{'name': tool, 'executable': '/usr/local/bin/' + tool + '-cli', 'safe_flags': [],
                          'health_check': 'craft capabilities ' + tool} for tool in profile['tools']],
        'skill_prompt_template': instructions,
        # This checks the declared capability map, not the quality of a deliverable.
        'verification_command': ' && '.join('craft capabilities ' + tool for tool in profile['tools']) or 'craft capabilities',
        'security_policy': {'rootless': True, 'network_access': False, 'writable_paths': ['$RIGHAVEN_OUTPUT_DIR']},
        'environment': {'purpose': profile['purpose'], 'tool_versions': profile['deployment'].get('tool_versions', {})},
    })
