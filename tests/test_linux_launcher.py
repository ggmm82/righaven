"""desktop/linux/righaven with a fake docker: settings, validation, files check, errors."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE_DOCKER = '''#!/bin/sh
echo "$*" >> "$FAKE_LOG"
case "$1 $2" in
  "info --format") [ -n "${FAKE_DENIED:-}" ] && { echo "permission denied while trying to connect" >&2; exit 1; }; echo "27.0.0";;
  "compose version") echo "${FAKE_COMPOSE:-2.29.1}";;
  *) exit 0;;
esac
'''


class LinuxLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.home = self.tmp / 'RigHaven'
        app = self.home / 'app'
        app.mkdir(parents=True)
        shutil.copy(ROOT / 'desktop/linux/righaven', self.home / 'righaven')
        files = {'compose.yaml': 'services: {}\n', 'Caddyfile': ':2026 {}\n'}
        for name, text in files.items():
            (app / name).write_text(text)
        release = {'version': '9.9.9', 'files': {n: hashlib.sha256(t.encode()).hexdigest() for n, t in files.items()}}
        (app / 'release.json').write_text(json.dumps(release, indent=2) + '\n')
        bin_dir = self.tmp / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'docker').write_text(FAKE_DOCKER)
        (bin_dir / 'docker').chmod(0o755)
        self.env = {'PATH': f'{bin_dir}:/usr/bin:/bin', 'LANG': 'en_US.UTF-8', 'FAKE_LOG': str(self.tmp / 'docker.log')}

    def run_launcher(self, *args, **env):
        return subprocess.run(['sh', str(self.home / 'righaven'), *args], capture_output=True, text=True,
                              env={**self.env, **env}, timeout=60)

    def test_version_and_files_check(self):
        self.assertEqual(self.run_launcher('version').stdout.strip(), 'RigHaven 9.9.9 (linux)')
        report = self.run_launcher('doctor').stdout
        self.assertIn('files: ok', report)
        self.assertIn('address: http://127.0.0.1:2026', report)
        (self.home / 'app/Caddyfile').write_text(':2026 { respond hacked }\n')
        self.assertIn('files: CHANGED Caddyfile', self.run_launcher('doctor').stdout)

    def test_options_are_validated_and_remembered(self):
        self.assertEqual(self.run_launcher('version', '--port', '80').returncode, 2)
        self.assertEqual(self.run_launcher('version', '--bind', 'localhost').returncode, 2)
        self.assertEqual(self.run_launcher('version', '--devices', '/dev/sda;rm').returncode, 2)
        self.assertEqual(self.run_launcher('version', '--name', 'Bad Name').returncode, 2)
        self.assertEqual(self.run_launcher('version', '--port', '2027', '--bind', '0.0.0.0', '--name', 'second').returncode, 0)
        settings = (self.home / 'data/settings').read_text()
        self.assertIn('port=2027', settings)
        report = self.run_launcher('doctor').stdout
        self.assertIn('project: second', report)
        self.assertIn('address: http://127.0.0.1:2027', report)  # browser address, never 0.0.0.0

    def test_docker_problems_are_explained(self):
        denied = self.run_launcher('status', FAKE_DENIED='1')
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn('docker group', denied.stderr)
        old = self.run_launcher('status', FAKE_COMPOSE='2.12.0')
        self.assertNotEqual(old.returncode, 0)
        self.assertIn('too old', old.stderr)
        self.assertIn('never started', self.run_launcher('status').stdout)

    def test_italian_messages(self):
        self.assertIn('mai avviato', self.run_launcher('status', LANG='it_IT.UTF-8').stdout)

    def test_remove_needs_typed_confirmation(self):
        result = subprocess.run(['sh', str(self.home / 'righaven'), 'remove'], input='no\n', capture_output=True,
                                text=True, env=self.env, timeout=60)
        self.assertIn('Cancelled', result.stdout)
        self.assertNotIn('down', (self.tmp / 'docker.log').read_text())


if __name__ == '__main__':
    unittest.main()
