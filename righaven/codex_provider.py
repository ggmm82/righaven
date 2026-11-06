"""RigHaven Codex provider adapted to the current Codex CLI wire format."""

import httpx

from righaven_core.models.openai_codex_provider import CodexChatModel

from .codex_compat import modernize_codex_payload
from .codex_transport import request_codex


class HarnessCodexChatModel(CodexChatModel):
    """Keep RigHaven's provider while matching current Codex request fields."""

    def _stream_response(self, headers: dict, payload: dict) -> dict:
        from .docker_runtime import refresh_codex_credentials
        for attempt in range(2):
            credential = self._load_codex_auth()
            if not credential:
                raise RuntimeError('Ricollega Codex nel pannello La tua squadra')
            current_headers = {**headers, 'Authorization': f'Bearer {credential.access_token}',
                               'ChatGPT-Account-ID': credential.account_id}
            try:
                return request_codex(current_headers, modernize_codex_payload(payload))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401 and attempt == 0:
                    refresh_codex_credentials()
                    continue
                try:
                    detail = exc.response.text.strip()
                except (httpx.ResponseNotRead, httpx.StreamClosed):
                    detail = ''
                detail = detail.replace(credential.access_token, '[REDACTED]')
                suffix = f": {detail[:2000]}" if detail else ''
                if exc.response.status_code in (429, 500, 529):
                    # Keep the pinned provider's bounded backoff/admission path.
                    # A RuntimeError here used to bypass its HTTP retry logic.
                    safe_request = httpx.Request('POST', str(exc.request.url))
                    safe_response = httpx.Response(exc.response.status_code,
                        content=detail, request=safe_request)
                    raise httpx.HTTPStatusError(
                        f'Codex API HTTP {exc.response.status_code}{suffix}',
                        request=safe_request, response=safe_response) from None
                raise RuntimeError(f"Codex API HTTP {exc.response.status_code}{suffix}") from None
