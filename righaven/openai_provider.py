"""Coordinator provider with private credentials selected by an opaque ID."""
import json
from langchain_openai import ChatOpenAI
from .state import custom_connection_path
from .tenant_profiles import TenantBoundModel, cloud_user


class HarnessCompatibleChatModel(TenantBoundModel, ChatOpenAI):
    def __init__(self, **kwargs):
        connection_id = kwargs.pop('connection_id', None)
        from .tenant_profiles import read_secret
        connection = read_secret(custom_connection_path(connection_id))
        kwargs.update(api_key=connection['api_key'], base_url=connection['base_url'], stream_usage=False)
        if cloud_user() is not None: kwargs['cache'] = False
        super().__init__(**kwargs)
        self.bind_tenant()
