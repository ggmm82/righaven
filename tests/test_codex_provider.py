"""Run against the real pinned RigHaven provider in the gateway image."""
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('righaven_core'), 'Requires pinned gateway dependencies')
class CodexProviderTests(unittest.TestCase):
    def test_native_agent_bootstrap_without_thinking_reaches_supported_transport(self):
        from langchain_core.messages import HumanMessage
        from righaven.codex_provider import HarnessCodexChatModel
        credential = SimpleNamespace(access_token='fixture-token', account_id='fixture-account')
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=credential):
            model = HarnessCodexChatModel(model='gpt-6.1-sol', reasoning_effort='none')
            with patch('righaven.codex_provider.request_codex', return_value={'output': []}) as transport:
                model._call_codex_api([HumanMessage('Create an Agent profile')])
        self.assertEqual(transport.call_args.args[1]['reasoning']['effort'], 'low')

    def test_transient_http_failure_reaches_native_bounded_retry(self):
        import httpx
        from langchain_core.messages import HumanMessage
        from righaven.codex_provider import HarnessCodexChatModel
        credential = SimpleNamespace(access_token='fixture-private-bearer', account_id='account')
        request = httpx.Request('POST', 'https://chatgpt.com/backend-api/codex/responses')
        response = httpx.Response(429, text='Rate limited fixture-private-bearer', request=request)
        failure = httpx.HTTPStatusError('Rate limited', request=request, response=response)
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=credential):
            model = HarnessCodexChatModel(model='gpt-6.1-sol')
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=credential), \
             patch('righaven.codex_provider.request_codex', side_effect=[failure, {'output': []}]) as transport, \
             patch('righaven_core.models.openai_codex_provider.time.sleep') as backoff:
            self.assertEqual(model._call_codex_api([HumanMessage('Prova')]), {'output': []})
        self.assertEqual(transport.call_count, 2)
        backoff.assert_called_once_with(2.0)

    def test_existing_model_uses_rotated_account_credentials_on_next_request(self):
        from righaven.codex_provider import HarnessCodexChatModel, CodexChatModel
        first = SimpleNamespace(access_token='fixture-old-bearer', account_id='old-account')
        rotated = SimpleNamespace(access_token='fixture-new-bearer', account_id='new-account')
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=first):
            model = HarnessCodexChatModel(model='gpt-5.4')
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=rotated), \
             patch('righaven.codex_provider.request_codex', return_value={'ok': True}) as request:
            model._stream_response({'Authorization': 'Bearer fixture-old-bearer'}, {'tools': []})
        headers, payload = request.call_args.args
        self.assertEqual(headers['Authorization'], 'Bearer fixture-new-bearer')
        self.assertEqual(headers['ChatGPT-Account-ID'], 'new-account')
        self.assertEqual(payload['tool_choice'], 'auto')
        self.assertIn('reasoning.encrypted_content', payload['include'])

    def test_provider_errors_do_not_reflect_current_bearer(self):
        import httpx
        from righaven.codex_provider import HarnessCodexChatModel, CodexChatModel
        credential = SimpleNamespace(access_token='fixture-private-bearer', account_id='fixture-account')
        response = httpx.Response(401, text='Rejected fixture-private-bearer',
                                  request=httpx.Request('POST', 'https://example.invalid'))
        failure = httpx.HTTPStatusError('Unauthorized', request=response.request, response=response)
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=credential):
            model = HarnessCodexChatModel(model='gpt-5.4')
            with patch('righaven.codex_provider.request_codex', side_effect=failure), \
                 patch('righaven.docker_runtime.refresh_codex_credentials'):
                with self.assertRaisesRegex(RuntimeError, r'HTTP 401.*\[REDACTED\]') as caught:
                    model._stream_response({}, {})
        self.assertNotIn(credential.access_token, str(caught.exception))

    def test_unauthorized_request_refreshes_cli_account_and_retries_once(self):
        import httpx
        from righaven.codex_provider import HarnessCodexChatModel, CodexChatModel
        first = SimpleNamespace(access_token='fixture-expired', account_id='account')
        renewed = SimpleNamespace(access_token='fixture-renewed', account_id='account')
        response = httpx.Response(401, request=httpx.Request('POST', 'https://example.invalid'))
        failure = httpx.HTTPStatusError('Expired', request=response.request, response=response)
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', return_value=first):
            model = HarnessCodexChatModel(model='gpt-5.4')
        with patch.object(HarnessCodexChatModel, '_load_codex_auth', side_effect=[first, renewed]), \
             patch('righaven.codex_provider.request_codex', side_effect=[failure, {'ok': True}]) as api, \
             patch('righaven.docker_runtime.refresh_codex_credentials') as refresh:
            self.assertEqual(model._stream_response({}, {}), {'ok': True})
        refresh.assert_called_once()
        self.assertEqual(api.call_args_list[1].args[0]['Authorization'], 'Bearer fixture-renewed')


if __name__ == '__main__':
    unittest.main()
