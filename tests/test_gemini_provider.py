"""Actual LangChain model contract, exercised in the pinned gateway image."""
import importlib.util
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('langchain_core'), 'Requires gateway dependencies')
class GeminiProviderTests(unittest.TestCase):
    def test_righaven_tool_call_and_final_answer_use_one_shared_model(self):
        from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
        from righaven.gemini_provider import HarnessGeminiChatModel
        calls = []
        def generate(payload, **kwargs):
            calls.append(payload)
            if len(calls) == 1:
                decision={'content':'','tool_calls':[{'name':'harness_delegate','args':{'agent':'gridcraft'}}]}
            else:
                self.assertIn('verified.xlsx',payload['prompt'])
                self.assertIn('harness_delegate',payload['prompt'])
                decision={'content':'Ecco il foglio verificato.','tool_calls':[]}
            return {**decision,'usage':{'input_tokens':10,'output_tokens':5,'total_tokens':15}}
        tools = [{'type': 'function', 'function': {'name': 'harness_delegate',
                  'parameters': {'type': 'object', 'properties': {'agent': {'type': 'string'}}}}}]
        model = HarnessGeminiChatModel(model='gemini-2.5-pro').bind_tools(tools)
        history = [SystemMessage('Italiano'), HumanMessage('Prepara il foglio')]
        with patch('righaven.docker_runtime.generate_gemini', side_effect=generate):
            first = model.invoke(history)
            history.extend([first, ToolMessage('{"output":"verified.xlsx"}', tool_call_id=first.tool_calls[0]['id'])])
            final = model.invoke(history)
        self.assertEqual(final.content, 'Ecco il foglio verificato.')
        self.assertEqual(final.usage_metadata['total_tokens'], 15)
        self.assertTrue(all(call['model'] == 'gemini-2.5-pro' for call in calls))


if __name__ == '__main__':
    unittest.main()
