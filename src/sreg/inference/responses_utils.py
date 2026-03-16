"""Utilities for migrating from Chat Completions to the Responses API.

Provides helpers for converting tool definitions and parsing responses.
"""

from __future__ import annotations

from typing import Any


def convert_tools_for_responses(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Chat Completions tool format to Responses API format.

    Chat Completions:
        {"type": "function", "function": {"name": "X", "description": "...", "parameters": {...}}}

    Responses API:
        {"type": "function", "name": "X", "description": "...", "parameters": {...}}
    """
    converted = []
    for tool in tools:
        if tool.get("type") == "function" and "function" in tool:
            fn = tool["function"]
            converted.append({
                "type": "function",
                "name": fn["name"],
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })
        elif tool.get("type") == "function" and "name" in tool:
            # Already in Responses API format
            converted.append(tool)
        else:
            converted.append(tool)
    return converted


__all__ = ["convert_tools_for_responses"]
