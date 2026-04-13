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
from typing import Any

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
    ):
        self.base = base_client
        self.max_iterations = max_iterations
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

        Adds python_exec and think tools, runs multi-turn loop using
        previous_response_id chaining (same pattern as engine.py solver),
        returns final text response.
        """
        # Fresh namespace for each question
        self._namespace = make_python_namespace()

        # Inject tool hint into system prompt
        enriched_messages = []
        for m in messages:
            if m.role == MessageRole.SYSTEM:
                enriched_messages.append(
                    Message(role=m.role, content=(m.content or "") + _TOOL_SYSTEM_ADDENDUM)
                )
            else:
                enriched_messages.append(m)

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

        # Multi-turn loop using previous_response_id chaining
        total_tokens = 0
        prev_response_id = None

        for iteration in range(self.max_iterations):
            if prev_response_id is None:
                # First call: send full messages
                response = self.base.chat(
                    messages=enriched_messages,
                    tools=all_tools,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                # Continuation: chain with previous response, send tool outputs
                response = self.base.chat(
                    messages=[],  # not used when previous_response_id is set
                    tools=all_tools,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    previous_response_id=prev_response_id,
                    raw_input=pending_tool_outputs,
                )

            total_tokens += (response.usage.total_tokens if response.usage else 0)
            prev_response_id = response.provider_response_id

            # If no tool calls, we're done
            if response.finish_reason != FinishReason.TOOL_CALLS or not response.tool_calls:
                if response.usage:
                    response.usage.total_tokens = total_tokens
                return response

            # Execute each tool call and build output items for next request
            pending_tool_outputs = []
            for tc in response.tool_calls:
                try:
                    args = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                except (json.JSONDecodeError, TypeError):
                    args = {}

                result_str = _handle_solver_tool(tc.name, args, self._namespace)

                pending_tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": tc.id or "",
                    "output": result_str,
                })

                logger.debug(
                    "Tool %s: %s -> %s",
                    tc.name,
                    str(args)[:100],
                    result_str[:100],
                )

        # Max iterations reached — return last response
        return response
