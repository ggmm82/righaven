"""Coordinator provider: keep the API key out of model configuration and responses."""
import json

from langchain_openai import ChatOpenAI

from .state import credential_dir
from .tenant_profiles import TenantBoundModel, cloud_user


class HarnessDeepSeekChatModel(TenantBoundModel, ChatOpenAI):
    def __init__(self, **kwargs):
        from .tenant_profiles import read_secret
        key = read_secret(credential_dir('deepseek') / 'api.json')['api_key']
        kwargs.update(api_key=key, base_url='https://api.deepseek.com',
                      extra_body={'thinking': {'type': 'disabled'}}, stream_usage=False)
        if cloud_user() is not None: kwargs['cache'] = False
        super().__init__(**kwargs)
        self.bind_tenant()
