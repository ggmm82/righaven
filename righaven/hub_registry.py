"""Pinned remote catalog distribution, independent of project execution."""
import hashlib
import json
import re
from urllib.parse import urlsplit
import httpx
from . import state
from .gallery import validate_pack_manifest

MAX_BYTES = 2 * 1024 * 1024


def settings():
    path = state.STATE / 'hub-registries.json'
    return json.loads(path.read_text()) if path.exists() else {}


def configure(name, url, sha256):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', name):
        raise ValueError('Invalid registry name')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Registry URL must use HTTPS without embedded credentials')
    if not re.fullmatch('[a-f0-9]{64}', sha256):
        raise ValueError('A SHA-256 catalog pin is required')
    with state.LOCK:
        value = settings()
        value[name] = {'url': url, 'sha256': sha256}
        state.atomic_json(state.STATE / 'hub-registries.json', value)
    return value[name]


def download(config):
    data = bytearray()
    with httpx.stream('GET', config['url'], timeout=20, follow_redirects=False, trust_env=True) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ValueError('Registry catalog exceeds 2 MiB')
    return bytes(data)


def sync(name, fetch=download):
    config = settings().get(name)
    if not config:
        raise ValueError('Unknown registry')
    try:
        data = fetch(config)
    except httpx.HTTPError as error:
        raise ValueError('Registry download failed; the previous catalog is retained') from error
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != config['sha256']:
        raise ValueError('Remote catalog checksum does not match the approved pin')
    value = json.loads(data)
    if not isinstance(value, dict) or not isinstance(value.get('packs'), list) or len(value['packs']) > 500:
        raise ValueError('Invalid registry catalog')
    packs = [validate_pack_manifest(pack) for pack in value['packs']]
    if len({p['id'] for p in packs}) != len(packs):
        raise ValueError('Duplicate remote pack identifiers')
    for pack in packs:
        pack['id'] = 'remote-' + name + '-' + pack['id']
        if len(pack['id']) > 64:
            raise ValueError('Namespaced pack identifier exceeds 64 characters')
        pack.update(registry=name, catalog_sha256=config['sha256'], verified=False,
                    stars=0, forks=0)
    # Publish only after every entry and the pinned bytes have been validated.
    state.atomic_json(state.STATE / 'hub-catalogs' / (name + '.json'), {'packs': packs})
    return {'registry': name, 'packs': len(packs), 'sha256': config['sha256']}


def remote_packs():
    root = state.STATE / 'hub-catalogs'
    result = []
    for path in sorted(root.glob('*.json')):
        result.extend(json.loads(path.read_text())['packs'])
    return result
