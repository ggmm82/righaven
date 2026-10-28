"""Compatibility helpers for the ChatGPT Codex Responses endpoint."""

from typing import Any


def modernize_codex_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Add fields emitted by current Codex CLI releases.

    RigHaven's pinned provider predates these fields.  The ChatGPT Codex
    endpoint validates the private Responses payload more strictly than the
    public API and otherwise answers with a generic HTTP 400.
    """
    compatible = dict(payload)
    # Native Agent bootstrap can disable thinking. The pinned factory maps
    # that to `none`, which gpt-6.1-sol rejects even though normal chat works.
    # Use its lowest supported level; preserve explicit valid user choices and
    # other models' contracts. Copy nested fields so retries retain the input.
    model = str(payload.get("model", ""))
    reasoning = payload.get("reasoning")
    if (model == "gpt-6.1-sol" or model.startswith("gpt-6.1-sol-")) and isinstance(reasoning, dict) and reasoning.get("effort") == "none":
        compatible["reasoning"] = {**reasoning, "effort": "low"}
    compatible.setdefault("tool_choice", "auto")
    compatible.setdefault("parallel_tool_calls", bool(compatible.get("tools")))
    compatible.setdefault("include", ["reasoning.encrypted_content"])
    return compatible
