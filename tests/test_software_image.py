import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import software_image as software


class SoftwareImageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);repo=Path(__file__).resolve().parents[1]
        for name in [*software.inputs(repo)['files'],'docker/Dockerfile.sandbox','config/software-image.lock.json']:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)

    def seed_verified_software(self):
        (self.root/'config/software-image.lock.json').write_text(json.dumps({
            'version': 1,
            'bootstrap': {
                'platform': 'linux/amd64',
                'fingerprint': software.fingerprint(self.root),
                'image': 'ghcr.io/ggmm82/righaven-sandbox@sha256:' + '3' * 64,
            },
        }))

    def test_worker_skills_and_frontend_do_not_invalidate_software(self):
        before=software.fingerprint(self.root)
        for name in ['righaven/run_agent.py','skills/custom/method/SKILL.md','frontend/page.tsx']:
            file=self.root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('changed')
        dockerfile=self.root/'docker/Dockerfile.sandbox';dockerfile.write_text(dockerfile.read_text()+'\n# new worker stage comment\n')
        self.assertEqual(before,software.fingerprint(self.root))
        self.assertNotEqual(before,software.fingerprint(self.root,'linux/arm64'))

    def test_program_lock_installers_and_software_instructions_change_identity(self):
        for name in ['versions.lock.json','scripts/install_antigravity.py','config/tool-capabilities.json','docker/Dockerfile.sandbox']:
            path=self.root/name;original=path.read_bytes();before=software.fingerprint(self.root)
            path.write_bytes(original+b'\n# changed\n' if name!='docker/Dockerfile.sandbox' else original.replace(b'USER root',b'USER root\nENV NEW_DEPENDENCY=1',1))
            self.assertNotEqual(before,software.fingerprint(self.root));path.write_bytes(original)

    def test_current_release_is_reused_without_rebuilding_or_switching_digest(self):
        self.seed_verified_software()
        with patch.object(software,'digest',side_effect=AssertionError('No fallback lookup')):
            first=software.resolve(self.root,'ggmm82/righaven')
            second=software.resolve(self.root,'ggmm82/righaven')
        self.assertTrue(first['reuse']);self.assertEqual(first,second)
        self.assertIn('@sha256:' + '3' * 64,first['image'])
        self.assertEqual(first['context'],'software=docker-image://'+first['image'])

    def test_changed_recipe_uses_a_published_input_key_or_requests_a_new_build(self):
        (self.root/'scripts/check_provider_clis.py').write_text('# new check')
        with patch.object(software,'digest',return_value='sha256:'+'a'*64):
            ready=software.resolve(self.root,'righaven/righaven')
        self.assertTrue(ready['reuse']);self.assertTrue(ready['image'].endswith('a'*64))
        with patch.object(software,'digest',return_value=None):
            missing=software.resolve(self.root,'righaven/righaven')
        self.assertFalse(missing['reuse']);self.assertEqual(missing['context'],'')

    def test_registry_auth_or_network_errors_do_not_trigger_reinstallation(self):
        for error in ['401 unauthorized','timeout while connecting']:
            with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],1,'',error)):
                with self.assertRaises(RuntimeError):software.digest('ghcr.io/repo/image:tag')
        with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','manifest unknown')):
            self.assertIsNone(software.digest('ghcr.io/repo/image:tag'))

    def test_existing_published_software_is_never_overwritten(self):
        self.seed_verified_software()
        selection=software.resolve(self.root,'ggmm82/righaven')
        with patch.object(software,'digest',return_value='sha256:'+'a'*64),patch.object(subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'non sovrascrivo'):software.publish(selection,selection['image'])
            run.assert_not_called()

    def test_unpinned_base_and_symlinked_inputs_are_rejected(self):
        path=self.root/'versions.lock.json';path.unlink();path.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):software.fingerprint(self.root)
        path.unlink();path.write_text('{}')
        dockerfile=self.root/'docker/Dockerfile.sandbox'
        dockerfile.write_text(dockerfile.read_text().replace('@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d',''))
        with self.assertRaisesRegex(ValueError,'digest'):software.fingerprint(self.root)

    def test_registry_digest_uses_root_descriptor_including_docker_schema_two(self):
        value='sha256:'+'b'*64
        output='Name: registry/image\nMediaType: application/vnd.docker.distribution.manifest.v2+json\nDigest: '+value+'\nManifests:\n  Digest: sha256:'+'c'*64+'\n'
        with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0,output,'')):
            self.assertEqual(software.digest('registry/image'),value)
