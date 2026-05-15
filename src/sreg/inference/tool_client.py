"""ModelClient wrapper that adds solver tools (python_exec, think) to any LLM call.

When benchmarks use this client instead of a plain OpenAIClient, the model
gets python_exec and think tools available. This is transparent to the
benchmark adapters — they call client.chat() as usual, but the model can
now analyze data with code execution.

Usage:
    from sreg.inference.openai_client import OpenAIClient
    from sreg.inference.tool_client import ToolEnrichedClient

    base_client = OpenAIClient(model="gpt-4o")
    client = ToolEnrichedClient(base_client)
    # Now benchmark adapters using this client get python_exec + think
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from sreg.agent.engine import SOLVER_TOOLS, _handle_solver_tool
from sreg.agent.python_exec import make_python_namespace
from sreg.inference.protocol import (
    ChatResponse,
    FinishReason,
    Message,
    MessageRole,
    ToolSpec,
    Usage,
)

logger = logging.getLogger(__name__)

# System prompt addition for tool-using benchmarks
_TOOL_SYSTEM_ADDENDUM = (
    "\n\nYou have access to a Python interpreter (python_exec tool) for data analysis. "
    "Use it to compute statistics, analyze data, and verify your reasoning. "
    "Pre-loaded: numpy (np), pandas (pd), scipy, math, statistics."
)


class ToolEnrichedClient:
    """ModelClient that adds python_exec and think tools to chat calls.

    Wraps another ModelClient. When chat() is called:
    1. Injects tool definitions (python_exec, think)
    2. Runs a multi-turn tool-calling loop
    3. Returns the final response as if it were a single chat() call

    The benchmark adapter sees a normal ChatResponse — it doesn't know
    that tool calling happened internally.
    """

    def __init__(
        self,
        base_client: Any,
        max_iterations: int = 8,
        namespace_factory: Callable[[], dict] | None = None,
    ):
        self.base = base_client
        self.max_iterations = max_iterations
        # Optional factory for custom namespaces (e.g. v1.5 Validators
        # inject `env`). If None, defaults to make_python_namespace().
        self._namespace_factory = namespace_factory
        # Fresh namespace per question (reset on each chat call)
        self._namespace: dict = {}

    def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Chat with tool-calling loop.

        Adds python_exec and think tools, runs multi-turn loop,
        returns final text response.
        """
        # Fresh namespace for each question (custom factory if provided).
        self._namespace = (
            self._namespace_factory() if self._namespace_factory is not None
            else make_python_namespace()
        )

        # Convert Messages to dicts for the base client
        msg_dicts = []
        for m in messages:
            d: dict[str, Any] = {"role": m.role.value, "content": m.content or ""}
            # Add tool hint to system prompt
            if m.role == MessageRole.SYSTEM:
                d["content"] = (m.content or "") + _TOOL_SYSTEM_ADDENDUM
            msg_dicts.append(d)

        # Build tool specs for OpenAI format
        solver_tool_specs = [
            ToolSpec(
                name=t["function"]["name"],
                description=t["function"]["description"],
                parameters=t["function"]["parameters"],
            )
            for t in SOLVER_TOOLS
        ]
        all_tools = list(solver_tool_specs)
        if tools:
            all_tools.extend(tools)

        # Multi-turn loop
        total_tokens = 0
        for iteration in range(self.max_iterations):
            response = self.base.chat(
                messages=[Message(**d) for d in msg_dicts],
                tools=all_tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            total_tokens += (response.usage.total_tokens if response.usage else 0)

            # If no tool calls, we're done
            if response.finish_reason != FinishReason.TOOL_CALLS or not response.tool_calls:
                # Return the final response with accumulated usage
                if response.usage:
                    response.usage.total_tokens = total_tokens
                return response

            # Append assistant message including its tool_calls so the
            # next request carries the function_call items (required by
            # the Responses API to match upcoming function_call_output).
            msg_dicts.append({
                "role": "assistant",
                "content": response.message.content or "",
                "tool_calls": [tc.model_dump() for tc in response.tool_calls],
            })

            # Detect terminal (non-solver) tool calls — return immediately
            # so the caller can process them (used by v1.5 Validators that
            # emit their final vote via a custom function call).
            solver_tool_names = {t["function"]["name"] for t in SOLVER_TOOLS}
            terminal_calls = [
                tc for tc in response.tool_calls if tc.name not in solver_tool_names
            ]
            if terminal_calls:
                if response.usage:
                    response.usage.total_tokens = total_tokens
                return response

            # Execute each solver tool call
            for tc in response.tool_calls:
                try:
                    args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                except (json.JSONDecodeError, TypeError):
                    args = {}

                result_str = _handle_solver_tool(tc.name, args, self._namespace)

                msg_dicts.append({
                    "role": "tool",
                    "tool_call_id": tc.id or "",
                    "content": result_str,
                })

                logger.debug(
                    "Tool %s: %s -> %s",
                    tc.name,
                    str(args)[:100],
                    result_str[:100],
                )

        # Max iterations reached — return last response
        return response
