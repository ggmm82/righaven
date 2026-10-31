"""Repository contracts that keep CI meaningful: lint coverage and stated facts."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def overlay_targets():
    targets = []
    for line in (ROOT / 'docker/Dockerfile.frontend').read_text().splitlines():
        if not line.startswith('COPY frontend/'):
            continue
        *sources, destination = line.split()[1:]
        for source in sources:
            if source.endswith(('.ts', '.tsx')):
                target = destination + source.rsplit('/', 1)[-1] if destination.endswith('/') else destination
                targets.append(target.removeprefix('./frontend/'))
    return targets


class LintBaselineTests(unittest.TestCase):
    def test_every_typescript_overlay_is_covered_by_the_eslint_gate(self):
        baseline = json.loads((ROOT / 'config/eslint-baseline.json').read_text())['files']
        self.assertEqual(sorted(baseline), sorted(overlay_targets()))
        self.assertTrue(all(type(n) is int and n >= 0 for rules in baseline.values() for n in rules.values()))


class DocumentedFactsTests(unittest.TestCase):
    """Numbers and versions written in the docs must match the repository they describe."""
    DOCS = ['README.md', *[f'docs/{name}' for name in ('AUDIT_AND_MAPPING.md', 'OPTIONAL-ENVIRONMENTS.md', 'POLICY-BOOK.md', 'technical-report.typ',
                                                       'c4/righaven.dsl', 'c4/righaven_containers.d2')]]

    def mentions(self, pattern):
        import re
        found = []
        for name in self.DOCS:
            path = ROOT / name
            if path.exists():
                found += [(name, m.group(1)) for m in re.finditer(pattern, path.read_text())]
        return found

    def test_tool_and_gallery_counts(self):
        tools = len(json.loads((ROOT / 'versions.lock.json').read_text())['applications'])
        packs = len(json.loads((ROOT / 'config/gallery-packs.json').read_text())['packs'])
        for name, value in self.mentions(r'(\d+) managed CLI tools'):
            self.assertEqual(int(value), tools, name)
        for name, value in self.mentions(r'catalog of (\d+\+?) Environment Rigs'):
            self.assertEqual(value, str(packs), name)
        self.assertTrue(self.mentions(r'(\d+) managed CLI tools'))

    def test_framework_and_service_versions(self):
        import re
        next_major = re.search(r'"next": "\D*(\d+)\.', (ROOT / 'core/frontend/package.json').read_text()).group(1)
        for name, value in self.mentions(r'Next\.js (\d+)'):
            self.assertEqual(value, next_major, name)
        redis = {re.search(r'image: redis:(\d+\.\d+)', (ROOT / f).read_text()).group(1) for f in ('docker-compose.yaml', 'config/compose.hostinger.template.yaml')}
        self.assertEqual(len(redis), 1)
        for name, value in self.mentions(r'Redis (\d+\.\d+)'):
            self.assertIn(value, redis, name)


if __name__ == '__main__':
    unittest.main()
