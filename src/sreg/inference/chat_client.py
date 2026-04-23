"""Chat Completions API adapter for the ModelClient protocol.

For vLLM, Ollama, and any OpenAI-compatible endpoint that exposes
/v1/chat/completions (NOT the Responses API).

Usage::

    # vLLM local
    client = ChatCompletionsClient(
        base_url="http://localhost:8000/v1",
        api_key="not-needed",
        model="Qwen/Qwen3-8B",
    )

    # Azure (Chat Completions path)
    client = ChatCompletionsClient()  # reads env vars
"""

from __future__ import annotations

import json
import logging
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

logger = logging.getLogger(__name__)

# Capability flag: this client does NOT support previous_response_id chaining
supports_previous_response_id = False


class ChatCompletionsClient:
    """ModelClient adapter using the Chat Completions API.

    Works with vLLM, Ollama, and any OpenAI-compatible server.
    Uses client.chat.completions.create() — NOT the Responses API.
    """

    supports_previous_response_id: bool = False

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        extra_body: dict[str, Any] | None = None,
    ):
        resolved_key = api_key or os.environ.get(
            "AZURE_INFERENCE_CREDENTIAL",
            os.environ.get("OPENAI_API_KEY", ""),
        )
        resolved_url = base_url or os.environ.get("AZURE_FOUNDRY_BASE_URL") or None
        self.default_model = model or os.environ.get("AZURE_MODEL", "gpt-4o")
        self._extra_body = extra_body or {}

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
        """Send a Chat Completions request and return a normalized response."""
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": _messages_to_chat_format(messages),
        }

        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = _tools_to_chat_format(tools)
        if self._extra_body:
            kwargs["extra_body"] = self._extra_body

        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            # Retry without temp/max_tokens for models that don't support them
            if "unsupported" in err_msg or "temperature" in err_msg or "max" in err_msg:
                kwargs.pop("temperature", None)
                kwargs.pop("max_tokens", None)
                response = self._client.chat.completions.create(**kwargs)
            else:
                raise

        return _parse_chat_response(response)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _messages_to_chat_format(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert protocol Messages to Chat Completions message dicts."""
    result = []
    for m in messages:
        msg: dict[str, Any] = {"role": m.role.value, "content": m.content}

        # Assistant message with tool calls
        if m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.raw_arguments or json.dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ]

        # Tool result message
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id

        result.append(msg)
    return result


def _tools_to_chat_format(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    """Convert protocol ToolSpecs to Chat Completions tool dicts."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _parse_chat_response(response: Any) -> ChatResponse:
    """Parse a Chat Completions response into a protocol ChatResponse."""
    choice = response.choices[0]
    message = choice.message

    # Parse tool calls (if any)
    tool_calls: list[ToolCall] = []
    if message.tool_calls:
        for tc in message.tool_calls:
            raw_args = tc.function.arguments
            try:
                args = json.loads(raw_args) if raw_args else {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                    raw_arguments=raw_args,
                )
            )

    # Determine finish reason
    if tool_calls:
        finish = FinishReason.TOOL_CALLS
    elif choice.finish_reason == "stop":
        finish = FinishReason.STOP
    elif choice.finish_reason == "length":
        finish = FinishReason.LENGTH
    else:
        finish = FinishReason.ERROR

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
            content=message.content,
        ),
        tool_calls=tool_calls,
        finish_reason=finish,
        usage=usage,
        provider_model=response.model,
    )
