"""Coordinator provider with private credentials selected by an opaque ID."""
import json
from langchain_openai import ChatOpenAI
from .state import custom_connection_path


class HarnessCompatibleChatModel(ChatOpenAI):
    def __init__(self, **kwargs):
        connection_id = kwargs.pop('connection_id', None)
        connection = json.loads(custom_connection_path(connection_id).read_text())
        kwargs.update(api_key=connection['api_key'], base_url=connection['base_url'], stream_usage=False)
        super().__init__(**kwargs)
