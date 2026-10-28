"""Software cache independence, immutable code delivery, no stale verifier reuse."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import runtime_bundle as bundle, state, environment_runtime as factory


class RuntimeBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'release'; (self.source / 'config').mkdir(parents=True)
        (self.source / 'scripts').mkdir(); (self.source / 'righaven').mkdir()
        (self.source / 'scripts/cli.py').write_text('print("adapter v1")')
        (self.source / 'righaven/run_agent.py').write_text('print("worker v1")')
        (self.source / 'config/worker-bundle.json').write_text(json.dumps({
            'righaven': {'cli.py': 'scripts/cli.py'}, 'righaven-worker': {'run_agent.py': 'righaven/run_agent.py'}}))
        for mock in (patch.object(state, 'STATE', self.root / 'state'),
                     patch.dict('os.environ', {'RIGHAVEN_WORKER_SOURCE': str(self.source)})):
            mock.start(); self.addCleanup(mock.stop)

    def test_code_update_reuses_software_recipe_but_keeps_active_bundle_immutable(self):
        with patch.object(factory, 'docker', return_value='sha256:software-stable'):
            before, _ = factory.recipe(['d2']); first = bundle.stage()
            (self.source / 'righaven/run_agent.py').write_text('print("worker v2")')
            after, _ = factory.recipe(['d2']); second = bundle.stage()
        self.assertEqual(before, after)
        self.assertNotEqual(first, second)
        self.assertIn('worker v1', (first / 'righaven-worker/run_agent.py').read_text())
        self.assertIn('worker v2', (second / 'righaven-worker/run_agent.py').read_text())
        self.assertEqual(second, bundle.stage())
        with patch.object(factory, 'docker', return_value='sha256:software-updated'):
            self.assertNotEqual(after, factory.recipe(['d2'])[0])

    def test_only_trusted_code_is_mounted_read_only_without_hiding_native_apps(self):
        from righaven import docker_runtime
        (self.source / 'scripts/not-in-bundle.py').write_text('do not deliver')
        with patch.object(docker_runtime, 'host_path', side_effect=str):
            args = bundle.arguments()
        mounts = [v for v in args if 'type=bind' in v]
        self.assertEqual(len(mounts), 2)
        self.assertTrue(all(v.endswith(',readonly') for v in mounts))
        self.assertTrue(any('dst=/opt/righaven/cli.py,' in v for v in mounts))
        self.assertFalse(any('dst=/opt/righaven,' in v for v in mounts))
        self.assertNotIn('not-in-bundle.py', str(args))
        self.assertNotIn('/credentials', str(args)); self.assertNotIn('docker.sock', str(args))
        self.assertNotIn('/mnt/user-data', str(args))

    def test_changed_adapter_invalidates_proofs_without_invalidating_software(self):
        from righaven.verification_cache import scope
        first = scope(self.root, self.root / 'chat', 'sha256:software')
        (self.source / 'scripts/cli.py').write_text('print("adapter v2")')
        self.assertNotEqual(first, scope(self.root, self.root / 'chat', 'sha256:software'))

    def test_modified_persistent_bundle_is_rejected(self):
        staged = bundle.stage()
        (staged / 'righaven-worker/run_agent.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'alterato'):bundle.stage()

    def test_symlink_in_trusted_manifest_is_rejected(self):
        path = self.source / 'righaven/run_agent.py'; path.unlink()
        path.symlink_to(self.source / 'scripts/cli.py')
        with self.assertRaisesRegex(ValueError, 'non valido'):bundle.stage()

    def test_every_standalone_worker_copy_has_a_bundle_equivalent(self):
        import shlex
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'config/worker-bundle.json').read_text())
        for line in (root / 'docker/Dockerfile.sandbox').read_text().split('FROM software AS core')[1].splitlines():
            if not line.startswith('COPY '):continue
            parts = shlex.split(line)[1:]
            if parts[-1] not in ('/opt/righaven-worker/', '/opt/righaven/'):continue
            for source in parts[:-1]:
                if Path(source).name in ('StructurizrJob.java','build_design_web.cjs'):continue
                self.assertEqual(manifest[parts[-1].split('/')[2]][Path(source).name], source)
    def test_ephemeral_cleanup_handles_a_software_identity_not_a_boolean_flag(self):
        from righaven.docker_runtime import release_prepared_environment
        with patch.object(factory,'evict') as evict:
            release_prepared_environment({'id':'a'*64,'core':'sha256:software','tools':['d2']},True)
            evict.assert_called_once_with('a'*64)
            evict.reset_mock()
            release_prepared_environment({'id':'a'*64,'core':True,'tools':[]},True)
            release_prepared_environment({'id':'a'*64,'core':'sha256:software','tools':['d2']},False)
            evict.assert_not_called()


if __name__ == '__main__':unittest.main()
