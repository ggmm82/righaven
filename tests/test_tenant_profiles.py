import contextvars
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
from righaven import state, tenant_profiles as tenants
from righaven.credential_sessions import ApiCredentialSession


class TenantProfilesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.user=contextvars.ContextVar('fixture-user',default='alice')
        for p in (patch.object(state,'STATE',Path(self.temp.name)),
                  patch.object(tenants,'cloud_user',side_effect=self.user.get),
                  patch.dict(os.environ,{'RIGHAVEN_CREDENTIALS_KEY':Fernet.generate_key().decode()})):
            p.start();self.addCleanup(p.stop)

    def test_private_profiles_and_encrypted_keys_do_not_fall_back_to_another_account(self):
        tenants.save('deepseek','deepseek-chat','alice-secret-api-key')
        alice=state.credential_dir('deepseek')/'api.json'
        self.assertNotIn('alice-secret-api-key',alice.read_text())
        self.assertEqual(tenants.read_secret(alice)['api_key'],'alice-secret-api-key')
        self.user.set('bob')
        with self.assertRaises(ValueError):tenants.profile('coordinator')
        bob=state.credential_dir('deepseek')/'api.json'
        self.assertNotEqual(alice,bob)
        self.assertFalse(bob.exists())
        tenants.save('deepseek','deepseek-reasoner','bob-secret-api-key')
        self.assertEqual(state.team()['model'],'deepseek-reasoner')
        self.user.set('alice')
        self.assertEqual(state.team()['model'],'deepseek-chat')

    def test_decrypted_worker_copy_is_private_and_removed_after_use(self):
        tenants.save('deepseek','deepseek-chat','alice-secret-api-key')
        destination=Path(self.temp.name)/'job-private'
        session=ApiCredentialSession('deepseek',destination)
        self.assertIn('alice-secret-api-key',(destination/'api.json').read_text())
        self.assertEqual(destination.stat().st_mode & 0o777,0o700)
        session.close();self.assertFalse(destination.exists())

    def test_model_instance_rejects_reuse_by_another_account(self):
        class Transport:
            def _generate(self):return 'sent'
        class Model(tenants.TenantBoundModel,Transport):pass
        model=Model();model.bind_tenant()
        self.assertEqual(model._generate(),'sent')
        self.user.set('bob')
        with self.assertRaisesRegex(ValueError,'different hosted account'):model._generate()

    def test_hosted_custom_endpoints_require_operator_approval(self):
        with self.assertRaisesRegex(ValueError,'approved'):
            tenants.save('openai','test','secret',base_url='https://internal.example/v1')
