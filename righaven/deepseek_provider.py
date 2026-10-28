"""Coordinator provider: keep the API key out of model configuration and responses."""
import json

from langchain_openai import ChatOpenAI

from .state import credential_dir


class HarnessDeepSeekChatModel(ChatOpenAI):
    def __init__(self, **kwargs):
        key = json.loads((credential_dir('deepseek') / 'api.json').read_text())['api_key']
        kwargs.update(api_key=key, base_url='https://api.deepseek.com',
                      extra_body={'thinking': {'type': 'disabled'}}, stream_usage=False)
        super().__init__(**kwargs)
