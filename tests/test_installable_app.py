"""The installable app (PWA): public manifest and icons, everything else behind the gate."""
from pathlib import Path
import re
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallableAppTests(unittest.TestCase):
    def test_only_manifest_icons_and_the_agent_endpoints_bypass_the_password_gate(self):
        text = (ROOT / 'docker/Caddyfile').read_text()
        matcher = re.search(r'@protected not path ([^\n]+)', text)
        self.assertIsNotNone(matcher)
        self.assertEqual(matcher.group(1).split(), ['/manifest.webmanifest', '/rh-app/*', '/api/webhooks/righaven-agent/*'])
        self.assertIn('basic_auth @protected {', text)
        self.assertEqual(text.count('basic_auth'), 1)

    def test_manifest_icons_exist_with_declared_sizes(self):
        manifest = (ROOT / 'core/frontend/src/app/manifest.ts').read_text()
        icons = re.findall(r'src: "(/rh-app/[^"]+)", sizes: "(\d+)x(\d+)"', manifest)
        self.assertEqual(len(icons), 3)
        for src, width, height in icons + [('/rh-app/apple-touch-icon.png', '180', '180')]:
            data = (ROOT / 'core/frontend/public' / src.lstrip('/')).read_bytes()
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n', src)
            self.assertEqual(struct.unpack('>II', data[16:24]), (int(width), int(height)), src)
        self.assertIn('display: "standalone"', manifest)
        self.assertIn('purpose: "maskable"', manifest)
        self.assertIn('/rh-app/apple-touch-icon.png', (ROOT / 'core/frontend/src/app/layout.tsx').read_text())


if __name__ == '__main__':
    unittest.main()
