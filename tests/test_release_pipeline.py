"""Test provenance, content equality and immutable Compose promotion without builds."""
import copy
import contextlib
import io
import os
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

from scripts.prepare_hostinger import prepare
from scripts.release_pipeline import assemble, reusable, resolve, validate_bundle, validate_manifest, publish

REPOSITORY = 'righaven/righaven'
COMPONENTS = ('gateway', 'frontend', 'sandbox', 'proxy')


def manifest():
    return {'version': 1, 'repository': REPOSITORY, 'workflow': '.github/workflows/verify.yml',
            'event': 'pull_request', 'run_id': 101, 'run_attempt': 1, 'source_commit': 'a' * 40,
            'tree': 'b' * 40, 'pull_request': 4, 'head_sha': 'c' * 40,
            'head_repository': REPOSITORY, 'verified': True,
            'images': {c: f'ghcr.io/{REPOSITORY}-{c}@sha256:' + str(i) * 64
                       for i, c in enumerate(COMPONENTS, 1)}}


def pr():
    return {'number': 4, 'merged_at': '2026-10-15T00:00:00Z', 'merge_commit_sha': 'd' * 40,
            'head': {'sha': 'c' * 40, 'repo': {'full_name': REPOSITORY}},
            'base': {'ref': 'main', 'repo': {'full_name': REPOSITORY}}}


def successful_run():
    return {'id': 101, 'run_attempt': 1, 'head_sha': 'c' * 40, 'event': 'pull_request',
            'head_repository': {'full_name': REPOSITORY}, 'conclusion': 'success',
            'path': '.github/workflows/verify.yml'}


def write_bundle(directory, value=None):
    directory = Path(directory)
    value = copy.deepcopy(value or manifest())
    prepare(value['source_commit'], directory / 'compose.hostinger.yaml',
            images=value['images'], inspect=lambda image: None)
    value['compose_sha256'] = hashlib.sha256((directory / 'compose.hostinger.yaml').read_bytes()).hexdigest()
    (directory / 'runtime-manifest.json').write_text(json.dumps(value))
    return value


class ReleasePipelineTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()
        self.addCleanup(self.stdout.__exit__, None, None, None)

    def test_compose_uses_same_digests_and_preserves_deployment_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            value = write_bundle(directory)
            result = validate_bundle(directory, REPOSITORY, 'b' * 40)
            self.assertEqual(result['images'], value['images'])
            compose = yaml.safe_load((Path(directory) / 'compose.hostinger.yaml').read_text())
            self.assertEqual(compose['services']['gateway']['environment']['RIGHAVEN_SANDBOX_IMAGE'], value['images']['sandbox'])
            self.assertTrue(compose['services']['runtime-docker']['privileged'])
            self.assertIn('runtime-docker-data', compose['volumes'])
            self.assertFalse(any('docker.sock' in str(v) for service in compose['services'].values() for v in service.get('volumes',[])))
            self.assertIn('righaven-data', compose['volumes'])
            self.assertNotIn('ports', compose['services']['gateway'])
            self.assertIn('${TRAEFIK_HOST', compose['services']['frontend']['environment']['BETTER_AUTH_URL'])
            self.assertTrue(reusable(value, REPOSITORY, 'b' * 40, pr(), successful_run()))
            # A rerun of only the final publication can reuse the earlier successful checks.
            rerun = {**successful_run(), 'run_attempt': 2}
            self.assertTrue(reusable(value, REPOSITORY, 'b' * 40, pr(), rerun))

    def test_changed_tree_head_failed_run_or_fork_cannot_be_promoted(self):
        value = manifest()
        for tree, pull, job in [
                ('e' * 40, pr(), successful_run()),
                ('b' * 40, {**pr(), 'head': {'sha': 'f' * 40}}, successful_run()),
                ('b' * 40, pr(), {**successful_run(), 'conclusion': 'failure'}),
                ('b' * 40, pr(), {**successful_run(), 'head_repository': {'full_name': 'other/fork'}}),
                ('b' * 40, pr(), {**successful_run(), 'id': 999}),
                ('b' * 40, pr(), {**successful_run(), 'path': '.github/workflows/other.yml'})]:
            with self.subTest(tree=tree, pull=pull, job=job):
                self.assertFalse(reusable(value, REPOSITORY, tree, pull, job))
        with self.assertRaisesRegex(ValueError, 'Avvio completo'):
            validate_manifest({**value, 'verified': False}, REPOSITORY, verified=True)

    def test_candidate_sealing_still_requires_unit_tests_when_builds_run_in_parallel(self):
        workflow=yaml.safe_load((Path(__file__).resolve().parents[1]/'.github/workflows/verify.yml').read_text())
        required=workflow['jobs']['startup']['needs']
        self.assertIn('tests',required)
        self.assertIn('images',required)
        self.assertIn('startup',workflow['jobs']['release']['needs'])

    def test_mixed_run_receipts_and_mutable_or_foreign_images_are_rejected(self):
        value = manifest()
        metadata = {k: v for k, v in value.items() if k not in ('images', 'verified')}
        with tempfile.TemporaryDirectory() as directory:
            for c, image in value['images'].items():
                (Path(directory) / (c + '.json')).write_text(json.dumps({'metadata': metadata, 'component': c, 'image': image}))
            self.assertEqual(assemble(directory, metadata)['images'], value['images'])
            bad = {**metadata, 'run_id': 202}
            (Path(directory) / 'gateway.json').write_text(json.dumps({'metadata': bad, 'component': 'gateway', 'image': value['images']['gateway']}))
            with self.assertRaisesRegex(ValueError, 'verifiche diverse'):
                assemble(directory, metadata)
        for image in ['ghcr.io/other/image@sha256:' + '1' * 64, f'ghcr.io/{REPOSITORY}-gateway:latest']:
            bad = copy.deepcopy(value)
            bad['images']['gateway'] = image
            with self.assertRaisesRegex(ValueError, 'immutabile'):
                validate_manifest(bad, REPOSITORY)

    def test_modified_compose_or_worker_reference_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            value = write_bundle(directory)
            path = Path(directory) / 'compose.hostinger.yaml'
            path.write_text(path.read_text() + '# modified\n')
            with self.assertRaisesRegex(ValueError, 'Compose diverso'):
                validate_bundle(directory, REPOSITORY)
            # Even a newly computed checksum cannot hide images not matching the proof.
            compose = yaml.safe_load(path.read_text())
            compose['services']['gateway']['environment']['RIGHAVEN_SANDBOX_IMAGE'] = 'wrong:latest'
            path.write_text(yaml.safe_dump(compose))
            value['compose_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            (Path(directory) / 'runtime-manifest.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'worker diversa'):
                validate_bundle(directory, REPOSITORY)

    def test_merge_selects_successful_pr_bundle_without_rebuilding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = write_bundle(root)
            def github(repo, path):
                return [pr()] if path.startswith('commits/') else {'workflow_runs': [successful_run()]}
            def download(run_id, target):
                self.assertEqual(run_id, 101)
                for name in ['runtime-manifest.json', 'compose.hostinger.yaml']:
                    (Path(target) / name).write_bytes((root / name).read_bytes())
            with patch('scripts.release_pipeline.run', return_value='b' * 40):
                self.assertTrue(resolve(REPOSITORY, 'd' * 40, root / 'reused', github=github, download=download))
            self.assertEqual((root / 'compose.hostinger.yaml').read_bytes(), (root / 'reused/compose.hostinger.yaml').read_bytes())
            self.assertEqual(validate_bundle(root / 'reused', REPOSITORY)['images'], original['images'])
            with patch('scripts.release_pipeline.run', return_value='e' * 40):
                self.assertFalse(resolve(REPOSITORY, 'd' * 40, root / 'changed', github=github, download=download))
            self.assertFalse((root / 'changed').exists())

    def test_preview_publishes_draft_assets_before_release_and_never_latest(self):
        with tempfile.TemporaryDirectory() as directory:
            write_bundle(directory)
            calls = []
            def command(*args):
                calls.append(args)
                return 'b' * 40 if args[0] == 'git' else ''
            with patch('scripts.release_pipeline.run', side_effect=command), \
                 patch('scripts.release_pipeline.api', return_value=pr()), \
                 patch('scripts.release_pipeline.subprocess.run') as subprocess_run:
                subprocess_run.return_value.returncode = 1
                publish(directory, REPOSITORY, 'a' * 40, main=False)
            create = next(c for c in calls if c[:3] == ('gh', 'release', 'create'))
            edit = next(c for c in calls if c[:3] == ('gh', 'release', 'edit'))
            self.assertIn('--draft', create)
            self.assertIn('--prerelease', create)
            self.assertIn('--latest=false', edit)
            self.assertNotIn('--latest=true', edit)
            self.assertTrue(any(c.endswith('compose.hostinger.yaml') for c in create))

    def test_main_promotes_exact_preview_without_docker_or_build_and_refuses_stale_main(self):
        with tempfile.TemporaryDirectory() as directory:
            original = write_bundle(directory)
            calls = []
            def command(*args):
                calls.append(args)
                return 'b' * 40 if args[0] == 'git' else ''
            with patch('scripts.release_pipeline.run', side_effect=command), \
                 patch('scripts.release_pipeline.api', return_value={'object': {'sha': 'd' * 40}}), \
                 patch('scripts.release_pipeline.subprocess.run') as subprocess_run:
                subprocess_run.return_value.returncode = 1
                publish(directory, REPOSITORY, 'd' * 40, main=True)
            self.assertFalse(any(c[0] == 'docker' for c in calls))
            edit = next(c for c in calls if c[:3] == ('gh', 'release', 'edit'))
            self.assertIn('--latest=true', edit)
            self.assertEqual(validate_bundle(directory, REPOSITORY)['images'], original['images'])
            with patch('scripts.release_pipeline.run', return_value='b' * 40), \
                 patch('scripts.release_pipeline.api', return_value={'object': {'sha': 'e' * 40}}):
                with self.assertRaisesRegex(ValueError, 'main è avanzato'):
                    publish(directory, REPOSITORY, 'd' * 40, main=True)


if __name__ == '__main__':
    unittest.main()
