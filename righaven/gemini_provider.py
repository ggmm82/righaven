"""Antigravity coordinator over the official CLI. Legacy class path preserves saved profiles."""
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

from . import antigravity_protocol


class HarnessGeminiChatModel(BaseChatModel):
    model: str = 'auto'
    request_timeout: int = 1800

    @property
    def _llm_type(self):
        return 'harness-antigravity-cli'

    @property
    def _identifying_params(self):
        return {'model': self.model}

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self.bind(tools=[convert_to_openai_tool(t) for t in tools],
                         tool_choice=tool_choice, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        from .docker_runtime import generate_gemini
        records = []
        for message in messages:
            value = {'type': message.type, 'content': message.content}
            if message.type == 'ai':
                value.update(tool_calls=message.tool_calls)
            if message.type == 'tool':
                value['tool_call_id'] = message.tool_call_id
            records.append(value)
        tools = kwargs.get('tools', [])
        payload = antigravity_protocol.request(records, self.model, tools, kwargs.get('tool_choice'))
        result = generate_gemini(payload, timeout=min(self.request_timeout, 1800))
        parsed = antigravity_protocol.response(result, tools)
        usage = result.get('usage', {})
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        message = AIMessage(content=parsed['content'], tool_calls=parsed['tool_calls'],
            usage_metadata={'input_tokens': input_tokens, 'output_tokens': output_tokens,
                            'total_tokens': max(usage.get('total_tokens', 0), input_tokens + output_tokens)})
        return ChatResult(generations=[ChatGeneration(message=message)])
