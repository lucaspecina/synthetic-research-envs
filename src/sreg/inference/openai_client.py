"""OpenAI SDK adapter for the ModelClient protocol.

Supports both OpenAI-native and Azure AI Foundry endpoints via base_url.
Uses the Responses API (not Chat Completions) for broad model compatibility
including reasoning models like gpt-5.2-codex.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolCall,
    ToolSpec,
    Usage,
)

load_dotenv()


class OpenAIClient:
    """ModelClient adapter for OpenAI-compatible APIs.

    Works with OpenAI, Azure AI Foundry, and any OpenAI-compatible endpoint.
    Uses the Responses API (not Chat Completions).

    Usage::

        # Azure AI Foundry (reads env vars by default)
        client = OpenAIClient()

        # OpenAI native
        client = OpenAIClient(api_key="sk-...", base_url=None)

        # Custom endpoint
        client = OpenAIClient(api_key="key", base_url="http://localhost:8000/v1")
    """

    supports_previous_response_id: bool = True

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        resolved_key = api_key or os.environ.get(
            "AZURE_INFERENCE_CREDENTIAL",
            os.environ.get("OPENAI_API_KEY", ""),
        )
        resolved_url = base_url or os.environ.get("AZURE_FOUNDRY_BASE_URL") or None
        self.default_model = model or os.environ.get("AZURE_MODEL", "gpt-4o")

        kwargs: dict[str, Any] = {"api_key": resolved_key}
        if resolved_url:
            kwargs["base_url"] = resolved_url

        self._client = OpenAI(**kwargs)

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        previous_response_id: str | None = None,
        raw_input: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
        """Send a request via the Responses API and return a normalized response.

        For multi-turn tool calling, use previous_response_id + raw_input
        (function_call_output items) instead of rebuilding the full message
        history. This matches how the Responses API chains requests.
        """
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
        }

        if previous_response_id and raw_input is not None:
            # Continuation: chain with previous response, send only tool outputs
            kwargs["previous_response_id"] = previous_response_id
            kwargs["input"] = raw_input
        else:
            # First call: extract system prompt and build input items
            instructions = None
            input_items: list[dict[str, Any]] = []
            for m in messages:
                if m.role == MessageRole.SYSTEM:
                    instructions = m.content
                elif m.role == MessageRole.USER:
                    input_items.append({"role": "user", "content": m.content or ""})
                elif m.role == MessageRole.ASSISTANT:
                    input_items.append({"role": "assistant", "content": m.content or ""})
                elif m.role == MessageRole.TOOL:
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": m.tool_call_id or "",
                        "output": m.content or "",
                    })
            kwargs["input"] = input_items if input_items else ""
            if instructions:
                kwargs["instructions"] = instructions

        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = [_toolspec_to_responses(t) for t in tools]

        try:
            response = self._client.responses.create(**kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            if "unsupported" in err_msg or "temperature" in err_msg or "max" in err_msg:
                kwargs.pop("temperature", None)
                kwargs.pop("max_output_tokens", None)
                response = self._client.responses.create(**kwargs)
            else:
                raise
        return _parse_responses_api(response)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _toolspec_to_responses(spec: ToolSpec) -> dict[str, Any]:
    """Convert a protocol ToolSpec to a Responses API function-tool dict."""
    return {
        "type": "function",
        "name": spec.name,
        "description": spec.description,
        "parameters": spec.parameters,
    }


def _parse_responses_api(response: Any) -> ChatResponse:
    """Parse a Responses API response into a protocol ChatResponse."""
    text_content = None
    tool_calls: list[ToolCall] = []

    for item in response.output:
        if item.type == "message":
            # Extract text from message content
            for part in item.content:
                if hasattr(part, "text"):
                    text_content = (text_content or "") + part.text
        elif item.type == "function_call":
            raw = item.arguments
            try:
                args = json.loads(raw) if raw else {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(
                ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=args,
                    raw_arguments=raw,
                )
            )

    # Determine finish reason
    if tool_calls:
        finish = FinishReason.TOOL_CALLS
    elif response.status == "completed":
        finish = FinishReason.STOP
    else:
        finish = FinishReason.ERROR

    # Parse usage
    usage = None
    if response.usage:
        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
        )

    return ChatResponse(
        message=Message(
            role=MessageRole.ASSISTANT,
            content=text_content,
        ),
        tool_calls=tool_calls,
        finish_reason=finish,
        usage=usage,
        provider_model=response.model,
        provider_response_id=response.id,
    )
