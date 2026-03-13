"""Inference abstraction: provider-agnostic LLM client protocol."""

from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ModelClient,
    ToolCall,
    ToolSpec,
    Usage,
)

__all__ = [
    "ChatResponse",
    "FinishReason",
    "Message",
    "MessageRole",
    "ModelClient",
    "ToolCall",
    "ToolSpec",
    "Usage",
]
