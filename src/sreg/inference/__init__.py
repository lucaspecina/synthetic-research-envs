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
from sreg.inference.responses_utils import convert_tools_for_responses

__all__ = [
    "ChatResponse",
    "FinishReason",
    "Message",
    "MessageRole",
    "ModelClient",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "convert_tools_for_responses",
]
