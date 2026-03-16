"""Shared tool-calling engine for LLM agents.

Provides a reusable tool-calling loop that works with any OpenAI-compatible
backend (Azure, vLLM, transformers). Used by:
- AgentSolver (diagnostic solving of SRCs)
- Benchmark adapters (CLadder, QRData, DiscoveryBench with tools)
- Training (via verifiers, which has its own loop)

The engine handles: tool dispatch, python_exec, think, multi-turn conversation.
Uses the Responses API for broad model compatibility (including reasoning models).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from openai import OpenAI

from sreg.agent.python_exec import ExecResult, execute_code, make_python_namespace
from sreg.inference.responses_utils import convert_tools_for_responses

logger = logging.getLogger(__name__)

# Tool definitions for the solver's own capabilities (not SREG environment tools)
SOLVER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": (
                "Execute Python code in a persistent interpreter (like a Jupyter notebook). "
                "Variables persist between calls. Pre-loaded: numpy (np), pandas (pd), "
                "scipy, math, statistics, json. Datasets available as `df`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute.",
                    }
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "think",
            "description": (
                "Use this tool to think through your reasoning step by step. "
                "Your reasoning will be recorded but has no side effects."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {
                        "type": "string",
                        "description": "Your step-by-step reasoning.",
                    }
                },
                "required": ["reasoning"],
            },
        },
    },
]


def _handle_solver_tool(
    name: str,
    args: dict,
    namespace: dict,
) -> str:
    """Handle a solver tool call (python_exec or think)."""
    if name == "think":
        return json.dumps({"status": "noted"})
    elif name == "python_exec":
        code = args.get("code", "")
        if not code:
            return "Error: no code provided."
        result: ExecResult = execute_code(code, namespace)
        return result.output
    else:
        return f"Error: unknown tool '{name}'."


def run_with_tools(
    client: OpenAI,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    tool_handler: Callable[[str, dict], str] | None = None,
    max_iterations: int = 15,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> list[dict]:
    """Run a multi-turn conversation with tool calling via the Responses API.

    This is the shared engine that powers both SRC solving and benchmark
    evaluation. It handles the tool-calling loop: send messages to LLM,
    dispatch tool calls, append results, repeat until done.

    Args:
        client: OpenAI-compatible client (Azure, vLLM, etc.)
        model: Model name/ID
        messages: Initial messages (system + user)
        tools: Tool definitions (OpenAI function format — auto-converted). None = no tools.
        tool_handler: Function(name, args) -> str to handle tool calls.
        max_iterations: Max tool-calling rounds.
        temperature: Sampling temperature (None = model default).
        max_tokens: Max tokens per response.

    Returns:
        Full message history including all tool calls and responses.
    """
    # Convert tools to Responses API format
    resp_tools = convert_tools_for_responses(tools) if tools else None

    # Extract system prompt from messages
    instructions = None
    initial_input = None
    for m in messages:
        if m.get("role") == "system":
            instructions = m.get("content", "")
        elif m.get("role") == "user":
            initial_input = m.get("content", "")

    prev_response_id = None

    for _ in range(max_iterations):
        kwargs: dict[str, Any] = {"model": model}
        if resp_tools:
            kwargs["tools"] = resp_tools
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens

        if prev_response_id is None:
            # First call
            if instructions:
                kwargs["instructions"] = instructions
            kwargs["input"] = initial_input or ""
        else:
            # Subsequent calls: chain with previous response
            kwargs["previous_response_id"] = prev_response_id
            kwargs["input"] = pending_tool_outputs

        try:
            response = client.responses.create(**kwargs)
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            # Try without unsupported params (reasoning models)
            kwargs.pop("temperature", None)
            kwargs.pop("max_output_tokens", None)
            try:
                response = client.responses.create(**kwargs)
            except Exception:
                raise

        prev_response_id = response.id

        # Parse output items
        text_content = None
        tool_calls = []
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        text_content = (text_content or "") + part.text
            elif item.type == "function_call":
                tool_calls.append(item)

        # Append assistant message to history
        assistant_msg: dict[str, Any] = {"role": "assistant", "content": text_content or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ]
        messages.append(assistant_msg)

        # If no tool calls, conversation is done
        if not tool_calls:
            break

        # Dispatch tool calls
        if tool_handler is None:
            break

        pending_tool_outputs = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.arguments)
            except json.JSONDecodeError:
                args = {}

            result_str = tool_handler(tc.name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.call_id,
                "content": result_str,
            })

            pending_tool_outputs.append({
                "type": "function_call_output",
                "call_id": tc.call_id,
                "output": result_str,
            })

    return messages


def solve_question(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    data: list[dict] | None = None,
    extra_tools: list[dict] | None = None,
    extra_handler: Callable[[str, dict], str | None] | None = None,
    max_iterations: int = 10,
    temperature: float | None = 0.0,
) -> str:
    """Solve a question using the full solver engine with tools.

    This is the high-level function for benchmarks: give it a question,
    optionally some data, and it returns the final text answer.

    The solver has python_exec and think tools available. If data is provided,
    it's pre-loaded as `df` in the python_exec namespace.

    Args:
        client: OpenAI-compatible client.
        model: Model name.
        system_prompt: System prompt for the solver.
        user_prompt: The question/task.
        data: Optional tabular data (list of dicts) to pre-load as df.
        extra_tools: Additional tool definitions beyond python_exec/think.
        extra_handler: Handler for extra tools. Returns None to fall through
            to default handler.
        max_iterations: Max tool-calling rounds.
        temperature: Sampling temperature.

    Returns:
        The final text response from the model.
    """
    # Build namespace with data if provided
    data_assets = None
    if data:
        data_assets = [{"data": data, "format": "tabular"}]
    namespace = make_python_namespace(data_assets=data_assets)

    # Combine tools
    tools = list(SOLVER_TOOLS)
    if extra_tools:
        tools.extend(extra_tools)

    # Build handler
    def handler(name: str, args: dict) -> str:
        if extra_handler:
            result = extra_handler(name, args)
            if result is not None:
                return result
        return _handle_solver_tool(name, args, namespace)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    messages = run_with_tools(
        client=client,
        model=model,
        messages=messages,
        tools=tools,
        tool_handler=handler,
        max_iterations=max_iterations,
        temperature=temperature,
    )

    # Extract final text response
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return msg["content"]

    return ""


__all__ = [
    "SOLVER_TOOLS",
    "run_with_tools",
    "solve_question",
]
