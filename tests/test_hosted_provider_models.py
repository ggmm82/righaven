"""Exercise the real LangChain provider classes with native user context, offline."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from righaven.openai_provider import HarnessCompatibleChatModel
    from righaven.deepseek_provider import HarnessDeepSeekChatModel
    from righaven_core.runtime.user_context import set_current_user, reset_current_user
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    HarnessCompatibleChatModel = None


@unittest.skipUnless(HarnessCompatibleChatModel, 'Gateway dependency environment required')
class HostedProviderModelsTests(unittest.TestCase):
    def test_disabled_profile_memory_does_not_initialize_a_provider(self):
        from righaven_core.agents.memory import manager
        with patch.object(manager, 'get_memory_config', return_value=SimpleNamespace(enabled=False)), \
             patch('righaven_core.models.create_chat_model') as factory:
            self.assertIsNone(manager._host_default_llm())
            factory.assert_not_called()

    def test_hosted_credentials_never_use_the_default_filesystem_user(self):
        from righaven import tenant_profiles
        with patch.dict(os.environ, {'RIGHAVEN_EDITION':'cloud'}):
            token = set_current_user(None)
            try:
                with self.assertRaises(RuntimeError):
                    tenant_profiles.root()
            finally:
                reset_current_user(token)

    def test_real_models_use_private_encrypted_connections_and_reject_cross_account_reuse(self):
        from cryptography.fernet import Fernet
        from righaven import state, tenant_profiles
        with tempfile.TemporaryDirectory() as folder, patch.object(state, 'STATE', Path(folder)), patch.dict(os.environ, {
            'RIGHAVEN_EDITION':'cloud', 'RIGHAVEN_CREDENTIALS_KEY':Fernet.generate_key().decode()}):
            token = set_current_user(SimpleNamespace(id='hosted-alice'))
            try:
                tenant_profiles.save('deepseek','deepseek-chat','private-alice-fixture')
                deepseek = HarnessDeepSeekChatModel(model='deepseek-chat')
                self.assertEqual(deepseek.openai_api_key.get_secret_value(),'private-alice-fixture')
                self.assertFalse(deepseek.cache)
                from righaven_core.config.model_config import ModelConfig
                original = ModelConfig(name='rh-codex', use='righaven.codex_provider:HarnessCodexChatModel',
                    model='operator-model', api_key='operator-secret', default_headers={'X-Account':'operator'},
                    base_url='https://operator.example', reasoning=True,
                    when_thinking_enabled={'reasoning_effort':'max'})
                private = tenant_profiles.model_config(original, 'rh-codex')
                self.assertEqual(private.model, 'deepseek-chat')
                for name in ('api_key','default_headers','base_url'):
                    self.assertNotIn(name, private.model_dump())
                self.assertIsNone(private.reasoning)
                self.assertIsNone(private.when_thinking_enabled)
                selected = tenant_profiles.save('openai','fixture-model','private-openai-fixture',base_url='https://api.openai.com/v1')
                compatible = HarnessCompatibleChatModel(model='fixture-model',connection_id=selected['connection_id'])
                self.assertEqual(compatible.openai_api_key.get_secret_value(),'private-openai-fixture')
                compatible.check_tenant()
                other = set_current_user(SimpleNamespace(id='hosted-bob'))
                try:
                    with self.assertRaisesRegex(ValueError,'different hosted account'):
                        compatible.check_tenant()
                    with self.assertRaisesRegex(ValueError,'Configure your private'):
                        tenant_profiles.profile('coordinator')
                    self.assertFalse(state.connection_status('deepseek'))
                finally:
                    reset_current_user(other)
            finally:
                reset_current_user(token)
