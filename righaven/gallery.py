"""RigHaven Community Gallery (On-Demand Hub) for Environments, CLI Tools, and Agent Skills."""
import json
import re
from pathlib import Path
from . import state
from .i18n import normalize_locale, translate

PACK_ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,63}\Z')
VALID_CATEGORIES = ('environment', 'cli-tool', 'skill')
REQUIRED_FIELDS = (
    'id', 'name', 'version', 'author', 'category', 'i18n',
    'docker_dependencies', 'cli_binaries', 'skill_prompt_template',
    'verification_command', 'security_policy',
)


def _builtin_catalog_path() -> Path:
    for candidate in (
        Path(__file__).with_name('gallery-packs.json'),
        Path(__file__).resolve().parents[1] / 'config/gallery-packs.json',
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError('Built-in gallery-packs.json not found')


def _community_store_path() -> Path:
    return state.STATE / 'gallery-community-packs.json'


def _activations_path() -> Path:
    return state.STATE / 'gallery-activations.json'


def validate_pack_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError('Pack manifest must be a JSON object')
    missing = [f for f in REQUIRED_FIELDS if f not in manifest]
    if missing:
        raise ValueError('Missing required righaven-pack.json fields: ' + ', '.join(missing))
    pack_id = manifest.get('id', '')
    if not isinstance(pack_id, str) or not PACK_ID_RE.fullmatch(pack_id):
        raise ValueError('Invalid pack id: must match ^[a-z0-9][a-z0-9-]{1,63}$')
    if manifest.get('category') not in VALID_CATEGORIES:
        raise ValueError('Invalid category: must be environment, cli-tool, or skill')
    for str_field in ('name', 'version', 'author', 'skill_prompt_template', 'verification_command'):
        val = manifest.get(str_field)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f'Field {str_field} must be a non-empty string')
    i18n = manifest.get('i18n')
    if not isinstance(i18n, dict) or 'en' not in i18n or 'it' not in i18n:
        raise ValueError('i18n must include both "en" and "it" translations')
    for lang in ('en', 'it'):
        entry = i18n.get(lang)
        if not isinstance(entry, dict) or not entry.get('title', '').strip() or not entry.get('description', '').strip():
            raise ValueError(f'i18n.{lang} requires non-empty title and description')
    deps = manifest.get('docker_dependencies')
    if not isinstance(deps, dict) or not isinstance(deps.get('base_image'), str):
        raise ValueError('docker_dependencies requires base_image and package lists')
    for pkg_list in ('system_packages', 'python_packages', 'node_packages'):
        if not isinstance(deps.get(pkg_list, []), list):
            raise ValueError(f'docker_dependencies.{pkg_list} must be a list')
    binaries = manifest.get('cli_binaries')
    if not isinstance(binaries, list):
        raise ValueError('cli_binaries must be a list')
    for b in binaries:
        if not isinstance(b, dict) or not b.get('name') or not b.get('executable') or not b.get('health_check'):
            raise ValueError('Each cli_binaries entry requires name, executable, safe_flags, and health_check')
    sec = manifest.get('security_policy')
    if not isinstance(sec, dict) or sec.get('rootless') is not True:
        raise ValueError('security_policy must enforce rootless=true')
    if '$RIGHAVEN_OUTPUT_DIR' not in sec.get('writable_paths', []):
        raise ValueError('security_policy.writable_paths must include $RIGHAVEN_OUTPUT_DIR')
    return {
        'id': pack_id,
        'name': manifest['name'].strip(),
        'version': manifest['version'].strip(),
        'author': manifest['author'].strip(),
        'category': manifest['category'],
        'tags': list(manifest.get('tags', [manifest['category']])),
        'stars': int(manifest.get('stars', 0)),
        'forks': int(manifest.get('forks', 0)),
        'verified': bool(manifest.get('verified', True)),
        'tools': list(manifest.get('tools', [])),
        'i18n': i18n,
        'docker_dependencies': deps,
        'cli_binaries': binaries,
        'skill_prompt_template': manifest['skill_prompt_template'].strip(),
        'verification_command': manifest['verification_command'].strip(),
        'security_policy': sec,
    }


def _all_packs() -> list[dict]:
    builtin = json.loads(_builtin_catalog_path().read_text(encoding='utf-8')).get('packs', [])
    community_path = _community_store_path()
    community = json.loads(community_path.read_text(encoding='utf-8')) if community_path.is_file() else []
    merged = {p['id']: dict(p) for p in builtin}
    for custom in community:
        merged[custom['id']] = dict(custom)
    return list(merged.values())


def localize_pack(pack: dict, locale: str = 'en') -> dict:
    norm = normalize_locale(locale)
    localized = pack.get('i18n', {}).get(norm) or pack.get('i18n', {}).get('en') or {}
    return {
        **pack,
        'display_title': localized.get('title', pack['name']),
        'display_description': localized.get('description', ''),
        'locale': norm,
    }


def list_packs(*, category: str | None = None, query: str | None = None, tag: str | None = None, locale: str = 'en', user_id: str = 'default') -> dict:
    norm = normalize_locale(locale)
    items = [localize_pack(p, norm) for p in _all_packs()]
    if category:
        if category not in VALID_CATEGORIES:
            raise ValueError(f'Unknown category: {category}')
        items = [p for p in items if p['category'] == category]
    if tag:
        t = tag.strip().lower()
        items = [p for p in items if t in [x.lower() for x in p.get('tags', [])]]
    if query:
        q = query.strip().lower()
        items = [
            p for p in items
            if q in p['id'].lower()
            or q in p['name'].lower()
            or q in p['display_title'].lower()
            or q in p['display_description'].lower()
            or any(q in t.lower() for t in p.get('tags', []))
        ]
    active_ids = set(active_packs_for(user_id))
    for item in items:
        item['activated'] = item['id'] in active_ids
    return {
        'hub_name': 'RigHaven Hub',
        'locale': norm,
        'total': len(items),
        'categories': {
            'environment': sum(1 for p in items if p['category'] == 'environment'),
            'cli-tool': sum(1 for p in items if p['category'] == 'cli-tool'),
            'skill': sum(1 for p in items if p['category'] == 'skill'),
        },
        'packs': items,
    }


def get_pack(pack_id: str, locale: str = 'en') -> dict:
    for p in _all_packs():
        if p['id'] == pack_id:
            return localize_pack(p, locale)
    raise KeyError(f"Pack '{pack_id}' not found in RigHaven Gallery")


def active_packs_for(user_id: str = 'default') -> list[str]:
    path = _activations_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    return list(data.get(user_id, []))


def activate_pack(pack_id: str, *, user_id: str = 'default', workspace: str | Path | None = None, locale: str = 'en') -> dict:
    pack = get_pack(pack_id, locale=locale)
    with state.LOCK:
        path = _activations_path()
        data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        current = list(dict.fromkeys([*data.get(user_id, []), pack_id]))
        data[user_id] = current
        state.atomic_json(path, data)
        if workspace:
            ws = Path(workspace).resolve()
            ws_manifest = ws / '.righaven-project/gallery-packs.json'
            ws_manifest.parent.mkdir(parents=True, exist_ok=True)
            ws_packs = json.loads(ws_manifest.read_text(encoding='utf-8')) if ws_manifest.is_file() else []
            if not any(p.get('id') == pack_id for p in ws_packs):
                ws_packs.append({
                    'id': pack['id'],
                    'category': pack['category'],
                    'version': pack['version'],
                    'tools': pack.get('tools', []),
                    'cli_binaries': pack.get('cli_binaries', []),
                    'verification_command': pack['verification_command'],
                })
                state.atomic_json(ws_manifest, ws_packs)
    return {
        'ok': True,
        'activated': True,
        'pack_id': pack_id,
        'category': pack['category'],
        'injected_tools': pack.get('tools', []),
        'verification_command': pack['verification_command'],
        'message': translate('notifications.pack_activated', locale=locale, id=pack_id),
        'pack': pack,
    }


def publish_pack(manifest: dict, *, locale: str = 'en') -> dict:
    validated = validate_pack_manifest(manifest)
    with state.LOCK:
        path = _community_store_path()
        existing = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
        existing = [p for p in existing if p.get('id') != validated['id']]
        existing.append(validated)
        state.atomic_json(path, existing)
    return {
        'ok': True,
        'published': True,
        'pack_id': validated['id'],
        'message': translate('notifications.pack_published', locale=locale, id=validated['id']),
        'pack': localize_pack(validated, locale=locale),
    }


def star_pack(pack_id: str, user_id: str = 'default', locale: str = 'en') -> dict:
    pack = get_pack(pack_id, locale=locale)
    with state.LOCK:
        path = _community_store_path()
        existing = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
        updated = dict(pack)
        updated['stars'] = int(updated.get('stars', 0)) + 1
        existing = [p for p in existing if p.get('id') != pack_id]
        existing.append(updated)
        state.atomic_json(path, existing)
    return {'ok': True, 'pack_id': pack_id, 'stars': updated['stars'], 'starred_by': user_id}


def fork_pack(pack_id: str, author: str, new_id: str | None = None, locale: str = 'en') -> dict:
    pack = get_pack(pack_id, locale=locale)
    fork_id = new_id or f"{pack_id}-fork-{author.lower()[:12]}"
    forked = {
        **pack,
        'id': re.sub(r'[^a-z0-9-]', '-', fork_id.lower()).strip('-')[:63],
        'author': author,
        'stars': 1,
        'forks': 0,
        'forked_from': pack_id,
    }
    return publish_pack(forked, locale=locale)
