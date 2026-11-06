#!/usr/bin/env python3
"""Turn a sealed release into the runtime files of the Windows portable app.

The portable app runs the same verified images as the server release, inside a
WSL 2 distribution managed by RigHaven.exe. Nothing is rebuilt: the release
Compose is validated, Traefik routing is replaced by the release's own proxy
image listening on 127.0.0.1 only, and the routes come from docker/Caddyfile
without the server password gate (the app has its own accounts).
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release_pipeline import validate_bundle  # noqa: E402

PORT = '${RIGHAVEN_PORT:-2026}'
# Matter controller (optional, profile "matter"): the official python-matter-server image, pinned.
MATTER_IMAGE = ('ghcr.io/home-assistant-libs/python-matter-server:8.1.0'
                '@sha256:170aa093ce91c76cde4cc390918307590f0f5558fcec93f913af3cb019e6562a')
# A fixed network for the portable Compose: its gateway is the host address where the Matter
# controller listens, reachable only from RigHaven's containers.
SUBNET, HOST_ADDRESS = '172.30.42.0/24', '172.30.42.1'
MATTER_URL = f'ws://{HOST_ADDRESS}:5580/ws'
LOCAL_URL = 'http://localhost:' + PORT
CADDYFILE = '/etc/caddy/Caddyfile.local'


def caddyfile(source=ROOT / 'docker/Caddyfile'):
    """Server routes, served on :2026 without the basic-auth gate."""
    text = Path(source).read_text()
    text, gates = re.subn(r'\n([ \t]*)basic_auth(?: @protected)? \{\n.*?\n\1\}\n', '\n', text, flags=re.S)
    text = re.sub(r'(\n[ \t]*#[^\n]*)*\n[ \t]*@protected [^\n]*', '', text)
    if gates != 1 or '{$RIGHAVEN_SITE}' not in text:
        raise ValueError('docker/Caddyfile changed: update prepare_desktop.py')
    text = text.replace('{$RIGHAVEN_SITE}', '{\n    admin off\n    auto_https off\n}\n\n:2026', 1)
    return text


def compose(release, manifest):
    content = yaml.safe_load(release)
    services = content['services']
    for service in services.values():
        service.pop('labels', None)
    for name in ('gateway', 'frontend'):
        services[name]['environment']['BETTER_AUTH_URL'] = LOCAL_URL
    gateway = services['gateway']['environment']
    # Set by the launcher of each platform (windows, linux).
    gateway['RIGHAVEN_DESKTOP'] = '${RIGHAVEN_DESKTOP:-windows}'
    # One person on one PC: devices and databases on the home or office network are expected.
    gateway['RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS'] = '${RIGHAVEN_CONNECTIONS_PRIVATE_NETWORKS:-allow}'
    gateway['RIGHAVEN_DEVICES'] = '${RIGHAVEN_DEVICES:-}'
    # The PC's local networks, detected by the launcher, offered to "Find devices on the network".
    gateway['RIGHAVEN_LOCAL_NETWORKS'] = '${RIGHAVEN_LOCAL_NETWORKS:-}'
    # Discovery reports written by the launcher (Bluetooth devices seen by the PC), read only.
    services['gateway'].setdefault('volumes', []).append('${RIGHAVEN_DISCOVERY_DIR:-./discovery}:/run/righaven/discovery:ro')
    # Requests from the page for the launcher (Bluetooth, USB, COM ports, Matter) and their results.
    services['gateway']['volumes'].append('${RIGHAVEN_HOST_DIR:-./host}:/run/righaven/host')
    services['proxy'] = {
        'restart': 'unless-stopped',
        'init': True,
        'image': manifest['images']['proxy'],
        'mem_limit': '96m',
        'entrypoint': ['caddy', 'run', '--config', CADDYFILE, '--adapter', 'caddyfile'],
        # Windows publishes it inside its own distribution; on Linux RIGHAVEN_BIND is the
        # address chosen with --bind (127.0.0.1 unless asked otherwise).
        'ports': ['${RIGHAVEN_BIND:-127.0.0.1}:' + PORT + ':2026'],
        'volumes': ['./Caddyfile:' + CADDYFILE + ':ro', 'caddy-data:/data', 'caddy-config:/config'],
        'depends_on': {'gateway': {'condition': 'service_healthy'}, 'frontend': {'condition': 'service_started'}},
    }
    # Matter devices are found with multicast and IPv6 on the local network: the controller uses
    # the host network and listens only on the RigHaven network gateway.
    services['matter'] = {
        'image': MATTER_IMAGE, 'profiles': ['matter'], 'restart': 'unless-stopped', 'network_mode': 'host', 'mem_limit': '512m',
        'command': ['--storage-path', '/data', '--paa-root-cert-dir', '/data/credentials', '--listen-address', HOST_ADDRESS, '--port', '5580'],
        'volumes': ['matter-data:/data'],
    }
    gateway['RIGHAVEN_MATTER_URL'] = '${RIGHAVEN_MATTER_URL:-}'
    content['networks'] = {'default': {'ipam': {'config': [{'subnet': SUBNET, 'gateway': HOST_ADDRESS}]}}}
    content.setdefault('volumes', {}).update({'caddy-data': {}, 'caddy-config': {}, 'matter-data': {}})
    text = yaml.safe_dump(content, sort_keys=False)
    if 'TRAEFIK_HOST' in text or 'traefik' in text:
        raise ValueError('Server routing left in the desktop Compose')
    return text


def prepare(release_directory, output, repository):
    release_directory, output = Path(release_directory), Path(output)
    manifest = validate_bundle(release_directory, repository)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        'compose.yaml': compose((release_directory / 'compose.hostinger.yaml').read_text(), manifest),
        'Caddyfile': caddyfile(),
    }
    for name, text in files.items():
        (output / name).write_text(text)
    release = {
        'version': manifest.get('release_version') or manifest['source_commit'][:12],
        'source_commit': manifest['source_commit'],
        'pull_request': manifest.get('pull_request'),
        'images': manifest['images'],
        'release_compose_sha256': manifest['compose_sha256'],
        'files': {name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
    }
    (output / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, required=True, help='Folder with compose.hostinger.yaml and runtime-manifest.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.release, args.output, args.repository)['version']))


if __name__ == '__main__':
    main()
