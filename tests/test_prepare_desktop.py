"""The Windows portable app runs exactly the verified release images, locally only."""
import json
from pathlib import Path
import tempfile
import unittest

import yaml

from scripts.prepare_desktop import caddyfile, prepare
from tests.test_release_pipeline import REPOSITORY, manifest, write_bundle

ROOT = Path(__file__).resolve().parents[1]


class PrepareDesktopTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.release = Path(self.folder.name) / 'release'
        self.release.mkdir()
        self.value = write_bundle(self.release, dict(manifest(), release_version=None))
        self.output = Path(self.folder.name) / 'app'

    def test_same_verified_images_served_only_on_localhost(self):
        release = prepare(self.release, self.output, REPOSITORY)
        compose = yaml.safe_load((self.output / 'compose.yaml').read_text())
        services = compose['services']
        self.assertEqual(services['gateway']['image'], self.value['images']['gateway'])
        self.assertEqual(services['frontend']['image'], self.value['images']['frontend'])
        self.assertEqual(services['proxy']['image'], self.value['images']['proxy'])
        self.assertEqual(services['gateway']['environment']['RIGHAVEN_SANDBOX_IMAGE'], self.value['images']['sandbox'])
        self.assertEqual(services['proxy']['ports'], ['${RIGHAVEN_BIND:-127.0.0.1}:${RIGHAVEN_PORT:-2026}:2026'])
        self.assertEqual(services['gateway']['environment']['RIGHAVEN_DESKTOP'], '${RIGHAVEN_DESKTOP:-windows}')
        # The optional Matter controller: pinned, host network, only on the RigHaven network gateway.
        matter = services['matter']
        self.assertEqual((matter['profiles'], matter['network_mode']), (['matter'], 'host'))
        self.assertIn('@sha256:', matter['image'])
        self.assertEqual(matter['command'][matter['command'].index('--listen-address') + 1], '172.30.42.1')
        self.assertEqual(compose['networks']['default']['ipam']['config'], [{'subnet': '172.30.42.0/24', 'gateway': '172.30.42.1'}])
        for name, service in services.items():
            self.assertNotIn('labels', service, name)
            if name != 'proxy':
                self.assertNotIn('ports', service, name)
        self.assertEqual(services['gateway']['environment']['BETTER_AUTH_URL'], 'http://localhost:${RIGHAVEN_PORT:-2026}')
        self.assertNotIn('TRAEFIK', (self.output / 'compose.yaml').read_text())
        # Isolation is unchanged: the same private nested runtime as the server.
        self.assertTrue(services['runtime-docker']['privileged'])
        self.assertEqual(services['gateway']['environment']['RIGHAVEN_DOCKER_SCOPE'], 'internal')
        self.assertEqual(release['images'], self.value['images'])
        self.assertEqual(json.loads((self.output / 'release.json').read_text())['source_commit'], self.value['source_commit'])

    def test_local_routes_match_the_server_proxy_without_the_password_gate(self):
        local, server = caddyfile(), (ROOT / 'docker/Caddyfile').read_text()
        self.assertNotIn('basic_auth', local)
        self.assertIn(':2026 {', local)
        self.assertIn('auto_https off', local)
        for route in ('handle @harness', 'handle /health*', 'handle /api/langgraph/*', 'uri replace /api/langgraph /api',
                      'handle /api/*', 'reverse_proxy frontend:3000'):
            self.assertIn(route, server)
            self.assertIn(route, local)

    def test_release_files_are_fingerprinted_for_the_doctor_command(self):
        release = prepare(self.release, self.output, REPOSITORY)
        import hashlib
        for name in ('compose.yaml', 'Caddyfile'):
            self.assertEqual(release['files'][name], hashlib.sha256((self.output / name).read_bytes()).hexdigest())

    def test_unverified_or_modified_release_is_refused(self):
        compose = self.release / 'compose.hostinger.yaml'
        compose.write_text(compose.read_text().replace('restart: unless-stopped', 'restart: always', 1))
        with self.assertRaises(ValueError):
            prepare(self.release, self.output, REPOSITORY)
        self.assertFalse((self.output / 'compose.yaml').exists())

    def test_rootfs_ships_every_script_the_launcher_calls(self):
        launcher = '\n'.join(p.read_text() for p in (ROOT / 'desktop/windows/launcher').glob('*.go'))
        scripts = {p.name for p in (ROOT / 'desktop/windows/rootfs/bin').iterdir()}
        for name in ('righaven-home', 'righaven-install', 'righaven-start', 'righaven-stop',
                     'righaven-status', 'righaven-logs', 'righaven-hold'):
            self.assertIn('/usr/local/bin/' + name, launcher)
            self.assertIn(name, scripts)
        selftest = (ROOT / 'desktop/windows/rootfs/bin/righaven-selftest').read_text()
        for name in scripts - {'righaven-selftest'}:
            self.assertIn(name.removeprefix('righaven-'), selftest)


if __name__ == '__main__':
    unittest.main()
