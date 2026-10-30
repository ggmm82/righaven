"""Boundary fixtures for CLI-only copying; native CLI execution runs in Compose CI."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import state,provider_bundle as provider


class ProviderBundleTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        fixtures=[patch.object(state,'STATE',self.root),patch.object(provider,'_CHECKED',{}),
            patch('righaven.tool_versions.selections',return_value={}),patch('righaven.tool_versions.resolved',return_value={}),
            patch('righaven.environment_runtime.ensure',return_value={'image_id':'sha256:cli'}),
            patch('righaven.environment_runtime.installation',return_value='test'),patch('righaven.environment_runtime.release_claim'),
            patch('righaven.docker_runtime.remove'),patch('righaven.docker_runtime.docker',side_effect=self.docker)]
        self.mocks=[]
        for fixture in fixtures:self.mocks.append(fixture.start());self.addCleanup(fixture.stop)
        self.ensure=self.mocks[4]

    def docker(self,*args,**kwargs):
        if args[0]=='cp':
            target=Path(args[-1])
            if '@openai' in args[-2]:
                entry=target/'codex/bin/codex.js';entry.parent.mkdir(parents=True);entry.write_text('// declared CLI fixture')
            else:target.write_text('#!/bin/sh\nexit 0\n')
        return 'fixture'

    def test_two_model_providers_reuse_software_instead_of_adding_provider_versions_to_it(self):
        first=provider.prepare('codex');second=provider.prepare('gemini')
        self.assertNotEqual(first[0],second[0])
        self.assertEqual([call.args[0] for call in self.ensure.call_args_list],[[],[]])
        with patch('righaven.docker_runtime.host_path',side_effect=str):args=provider.arguments(first)
        self.assertTrue(any('readonly' in str(value) for value in args))
        self.assertTrue(any('PATH='+provider.TARGET+'/bin:' in str(value) for value in args))

    def test_restart_reuses_exported_cli_without_preparing_any_image(self):
        first=provider.prepare('gemini');self.ensure.reset_mock()
        with patch.object(provider,'_CHECKED',{}):second=provider.prepare('gemini')
        self.assertEqual(first,second);self.ensure.assert_not_called()

    def test_a_modified_provider_payload_is_rejected_after_restart(self):
        root,value=provider.prepare('gemini');(root/'bin/agy').write_text('changed')
        with patch.object(provider,'_CHECKED',{}),self.assertRaisesRegex(ValueError,'alterato'):provider.prepare('gemini')

    def test_api_models_do_not_need_a_cli_runtime(self):
        self.assertIsNone(provider.prepare('deepseek'));self.assertIsNone(provider.prepare('openai'));self.ensure.assert_not_called()
