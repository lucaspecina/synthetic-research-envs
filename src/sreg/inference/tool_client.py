"""ModelClient wrapper that adds solver tools (python_exec, think) to any LLM call.

When benchmarks use this client instead of a plain OpenAIClient, the model
gets python_exec and think tools available. This is transparent to the
benchmark adapters — they call client.chat() as usual, but the model can
now analyze data with code execution.

Supports two backends:
- Responses API (OpenAIClient): uses previous_response_id chaining
- Chat Completions (ChatCompletionsClient / vLLM): rebuilds message history

Usage:
    from sreg.inference.openai_client import OpenAIClient
    from sreg.inference.chat_client import ChatCompletionsClient
    from sreg.inference.tool_client import ToolEnrichedClient

    # Azure (Responses API — chaining)
    base = OpenAIClient(model="gpt-5.4")
    client = ToolEnrichedClient(base)

    # vLLM (Chat Completions — history replay)
    base = ChatCompletionsClient(base_url="http://localhost:8000/v1", model="qwen3-8b")
    client = ToolEnrichedClient(base)
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
    ToolCall,
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

_TOOL_SYSTEM_DATA_ADDENDUM = (
    " The dataset is pre-loaded as `df` (pandas DataFrame). "
    "Additional datasets (if any) are available as `df_1`, `df_2`, etc."
)


class ToolEnrichedClient:
    """ModelClient that adds python_exec and think tools to chat calls.

    Wraps another ModelClient. When chat() is called:
    1. Injects tool definitions (python_exec, think)
    2. Runs a multi-turn tool-calling loop
    3. Returns the final response as if it were a single chat() call

    Automatically detects the backend capability:
    - If base client has supports_previous_response_id=True: uses Responses
      API chaining (efficient, sends only tool outputs per turn)
    - Otherwise: rebuilds full message history each turn (works with any
      Chat Completions-compatible server including vLLM)
    """

    def __init__(
        self,
        base_client: Any,
        max_iterations: int = 8,
        data_assets: list | None = None,
    ):
        self.base = base_client
        self.max_iterations = max_iterations
        self._data_assets = data_assets
        self._namespace: dict = {}
        # Detect backend capability
        self._use_chaining = getattr(base_client, "supports_previous_response_id", False)

    def set_data(self, data_assets: list | None) -> None:
        """Set per-question data assets for the next chat() call."""
        self._data_assets = data_assets

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
        # Fresh namespace for each question
        self._namespace = make_python_namespace(data_assets=self._data_assets)
        has_data = self._data_assets is not None and len(self._data_assets or []) > 0

        # Enrich system prompt with tool hint
        enriched_messages = _enrich_system_messages(messages, has_data)

        # Build combined tool specs
        all_tools = _build_tool_specs(tools)

        if self._use_chaining:
            return self._chat_with_chaining(
                enriched_messages, all_tools, model, temperature, max_tokens
            )
        else:
            return self._chat_with_history(
                enriched_messages, all_tools, model, temperature, max_tokens
            )

    # ------------------------------------------------------------------
    # Path A: Responses API chaining (previous_response_id)
    # ------------------------------------------------------------------

    def _chat_with_chaining(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> ChatResponse:
        """Multi-turn loop using previous_response_id (Responses API)."""
        total_tokens = 0
        prev_response_id = None

        for iteration in range(self.max_iterations):
            if prev_response_id is None:
                response = self.base.chat(
                    messages=messages,
                    tools=tools,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                response = self.base.chat(
                    messages=[],
                    tools=tools,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    previous_response_id=prev_response_id,
                    raw_input=pending_tool_outputs,
                )

            total_tokens += response.usage.total_tokens if response.usage else 0
            prev_response_id = response.provider_response_id

            if response.finish_reason != FinishReason.TOOL_CALLS or not response.tool_calls:
                content = response.message.content or ""
                if iteration == 0 and tools and (
                    "python_exec" in content or "function" in content.lower()
                ):
                    logger.warning(
                        "Model returned text mentioning tools but no tool_calls parsed. "
                        "Response preview: %s",
                        content[:200],
                    )
                if response.usage:
                    response.usage.total_tokens = total_tokens
                return response

            pending_tool_outputs = self._execute_tools(response.tool_calls)

        return response

    # ------------------------------------------------------------------
    # Path B: Message history replay (Chat Completions / vLLM)
    # ------------------------------------------------------------------

    def _chat_with_history(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> ChatResponse:
        """Multi-turn loop rebuilding full message history each turn."""
        total_tokens = 0
        conversation = list(messages)  # copy — don't mutate caller's list

        for iteration in range(self.max_iterations):
            response = self.base.chat(
                messages=conversation,
                tools=tools,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            total_tokens += response.usage.total_tokens if response.usage else 0

            if response.finish_reason != FinishReason.TOOL_CALLS or not response.tool_calls:
                # Warn if model returned text that looks like unparsed tool calls
                # (vLLM may fail to parse tool invocations and return raw text)
                content = response.message.content or ""
                if iteration == 0 and tools and (
                    "python_exec" in content or "function" in content.lower()
                ):
                    logger.warning(
                        "Model returned text mentioning tools but no tool_calls were parsed. "
                        "The model may be attempting tool use but the server didn't parse it. "
                        "Check vLLM --tool-call-parser and --enable-auto-tool-choice flags. "
                        "Response preview: %s",
                        content[:200],
                    )
                if response.usage:
                    response.usage.total_tokens = total_tokens
                return response

            # Append assistant message WITH tool_calls to history
            conversation.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=response.message.content,
                    tool_calls=response.tool_calls,
                )
            )

            # Execute tools and append results to history
            for tc in response.tool_calls:
                result_str = self._exec_single_tool(tc)
                conversation.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=result_str,
                        tool_call_id=tc.id,
                    )
                )

        return response

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _execute_tools(self, tool_calls: list[ToolCall]) -> list[dict]:
        """Execute tool calls and return Responses API formatted outputs."""
        outputs = []
        for tc in tool_calls:
            result_str = self._exec_single_tool(tc)
            outputs.append({
                "type": "function_call_output",
                "call_id": tc.id or "",
                "output": result_str,
            })
        return outputs

    def _exec_single_tool(self, tc: ToolCall) -> str:
        """Execute a single tool call and return the result string."""
        try:
            args = (
                json.loads(tc.arguments)
                if isinstance(tc.arguments, str)
                else tc.arguments
            )
        except (json.JSONDecodeError, TypeError):
            args = {}

        result_str = _handle_solver_tool(tc.name, args, self._namespace)

        logger.debug(
            "Tool %s: %s -> %s",
            tc.name,
            str(args)[:100],
            result_str[:100],
        )
        return result_str


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _enrich_system_messages(messages: list[Message], has_data: bool) -> list[Message]:
    """Inject tool availability hint into system messages."""
    addendum = _TOOL_SYSTEM_ADDENDUM
    if has_data:
        addendum += _TOOL_SYSTEM_DATA_ADDENDUM

    enriched = []
    for m in messages:
        if m.role == MessageRole.SYSTEM:
            enriched.append(
                Message(role=m.role, content=(m.content or "") + addendum)
            )
        else:
            enriched.append(m)
    return enriched


def _build_tool_specs(extra_tools: list[ToolSpec] | None = None) -> list[ToolSpec]:
    """Build solver tool specs + any extra tools from the caller."""
    solver_tool_specs = [
        ToolSpec(
            name=t["function"]["name"],
            description=t["function"]["description"],
            parameters=t["function"]["parameters"],
        )
        for t in SOLVER_TOOLS
    ]
    all_tools = list(solver_tool_specs)
    if extra_tools:
        all_tools.extend(extra_tools)
    return all_tools
