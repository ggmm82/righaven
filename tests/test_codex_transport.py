"""Exercise streamed HTTP responses, rather than preloaded error fixtures."""
import json
import unittest
from unittest.mock import patch

import httpx
from righaven.codex_transport import request_codex


class CodexTransportTests(unittest.TestCase):
    def test_bad_request_body_survives_closed_stream(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(400, stream=httpx.ByteStream(b'{"error":{"message":"Unsupported field"}}'))))
        with patch('righaven.codex_transport.httpx.Client', return_value=client):
            with self.assertRaises(httpx.HTTPStatusError) as error:
                request_codex({}, {})
        self.assertTrue(error.exception.response.is_closed)
        self.assertEqual(error.exception.response.json()['error']['message'], 'Unsupported field')

    def test_incremental_tool_item_and_final_answer_are_preserved(self):
        item = {'type': 'function_call', 'name': 'harness_delegate', 'call_id': 'call_1', 'arguments': '{}'}
        events = [{'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                  {'type': 'response.completed', 'response': {'output': [], 'usage': {'total_tokens': 5}}}]
        stream = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events).encode()
        client = httpx.Client(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, stream=httpx.ByteStream(stream))))
        with patch('righaven.codex_transport.httpx.Client', return_value=client):
            result = request_codex({}, {})
        self.assertEqual(result['output'], [item])
        self.assertEqual(result['usage']['total_tokens'], 5)
