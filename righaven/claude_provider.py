"""Claude Code coordinator using the official CLI and scoped tool decisions."""
from .gemini_provider import HarnessGeminiChatModel

class HarnessClaudeChatModel(HarnessGeminiChatModel):
    model:str='sonnet'

    @property
    def _llm_type(self):return 'righaven-claude-code-cli'

    @property
    def wire_protocol(self):
        from . import claude_protocol
        return claude_protocol

    def invoke_cli(self,payload):
        from .docker_runtime import generate_claude
        return generate_claude(payload,timeout=min(self.request_timeout,1800))
