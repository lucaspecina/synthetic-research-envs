"""Provider-agnostic LLM client protocol.

Shared contracts for inference across OpenAI API, vLLM, and other backends.
The goal is that agent, orchestrator, benchmarks, and RL training all use
the same interface — adapters handle provider-specific details.

These are DOMAIN contracts, not provider wrappers. Provider-specific shapes
(OpenAI function schemas, vLLM chat templates) live in adapter modules.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FinishReason(StrEnum):
    STOP = "stop"
    TOOL_CALLS = "tool_calls"
    LENGTH = "length"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Data transfer objects (concrete Pydantic models, not Protocols)
# ---------------------------------------------------------------------------


class Message(BaseModel):
    """A single message in a chat conversation."""

    role: MessageRole
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ToolSpec(BaseModel):
    """Tool definition exposed to the model (provider-agnostic)."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """A tool invocation returned by the model."""

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    raw_arguments: str | None = None


class Usage(BaseModel):
    """Token usage from a completion."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ChatResponse(BaseModel):
    """Normalized response from any LLM provider."""

    message: Message
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: FinishReason
    usage: Usage | None = None
    provider_model: str | None = None
    provider_response_id: str | None = None


# ---------------------------------------------------------------------------
# Client protocol (what adapters must implement)
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelClient(Protocol):
    """Minimal interface for LLM inference with tool calling.

    Adapters (OpenAI Responses API, vLLM, etc.) implement this protocol.
    The agent, orchestrator, and benchmarks program against it.
    """

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse: ...
