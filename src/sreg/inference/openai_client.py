"""OpenAI SDK adapter for the ModelClient protocol.

Supports both OpenAI-native and Azure AI Foundry endpoints via base_url.
Uses the openai SDK directly (NOT AzureOpenAI — see CLAUDE.md).
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

    Usage::

        # Azure AI Foundry (reads env vars by default)
        client = OpenAIClient()

        # OpenAI native
        client = OpenAIClient(api_key="sk-...", base_url=None)

        # Custom endpoint
        client = OpenAIClient(api_key="key", base_url="http://localhost:8000/v1")
    """

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
    ) -> ChatResponse:
        """Send a chat completion request and return a normalized response."""
        api_messages = [_message_to_dict(m) for m in messages]

        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": api_messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = [_toolspec_to_dict(t) for t in tools]

        response = self._client.chat.completions.create(**kwargs)
        return _parse_response(response)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _message_to_dict(msg: Message) -> dict[str, Any]:
    """Convert a protocol Message to an OpenAI API dict."""
    d: dict[str, Any] = {"role": msg.role.value}
    if msg.content is not None:
        d["content"] = msg.content
    if msg.tool_call_id is not None:
        d["tool_call_id"] = msg.tool_call_id
    if msg.name is not None:
        d["name"] = msg.name
    return d


def _toolspec_to_dict(spec: ToolSpec) -> dict[str, Any]:
    """Convert a protocol ToolSpec to an OpenAI function-tool dict."""
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": spec.parameters,
        },
    }


def _parse_response(response: Any) -> ChatResponse:
    """Parse an OpenAI API response into a protocol ChatResponse."""
    choice = response.choices[0]
    msg = choice.message

    # Parse tool calls
    tool_calls: list[ToolCall] = []
    if msg.tool_calls:
        for tc in msg.tool_calls:
            raw = tc.function.arguments
            try:
                args = json.loads(raw) if raw else {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                    raw_arguments=raw,
                )
            )

    # Map finish reason
    reason_map = {
        "stop": FinishReason.STOP,
        "tool_calls": FinishReason.TOOL_CALLS,
        "length": FinishReason.LENGTH,
    }
    finish = reason_map.get(choice.finish_reason, FinishReason.ERROR)

    # Parse usage
    usage = None
    if response.usage:
        usage = Usage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        )

    return ChatResponse(
        message=Message(
            role=MessageRole.ASSISTANT,
            content=msg.content,
        ),
        tool_calls=tool_calls,
        finish_reason=finish,
        usage=usage,
        provider_model=response.model,
        provider_response_id=response.id,
    )
