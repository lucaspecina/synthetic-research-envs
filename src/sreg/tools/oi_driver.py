"""OI Solver Driver: orchestrates the LLM <-> runner loop.

This is the missing orchestration layer that connects:
  LLM (solver) -> tool calls -> runner -> tool results -> LLM -> ... -> submit

Two modes:
  1. Real LLM: run_oi_investigation() uses a custom Responses API loop
     with OI-specific control flow (submit-is-terminal, deadline nudging).
  2. Scripted: run_oi_scripted() takes predetermined actions for testing.

The driver does NOT know about scoring internals (salience, compiler).
It only knows: prompt the solver, dispatch tool calls, return results.

Design: follows engine.py patterns (tool handler, Responses API chaining).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from sreg.models.open_investigation import (
    ClaimCard,
    EpisodeScore,
    EpisodeSubQuestionScore,
    EpisodeTrace,
)
from sreg.tools.oi_prompts import (
    build_oi_briefing,
    build_oi_strategy_section,
    build_oi_system_prompt,
    build_oi_tools_section,
)
from sreg.tools.oi_runner import OIEpisodeRunner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions for Responses API
# ---------------------------------------------------------------------------

OI_SOLVER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "python_exec",
            "description": (
                "Execute Python code in a persistent interpreter. Variables persist "
                "between calls. Pre-loaded: numpy (np), pandas (pd), scipy, math, "
                "statistics. Use load_artifact(id) to load datasets, "
                "save_artifact(df, label) to save derived data. Instrumented helpers: "
                "oi.corr, oi.regress, oi.stratify, oi.test_independence, oi.groupby_mean."
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
                "Think through your reasoning step by step. "
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
    {
        "type": "function",
        "function": {
            "name": "submit_claims",
            "description": (
                "Submit your research findings as structured claim cards. "
                "Call ONCE at the end of your investigation. 1-5 claims."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim_id": {
                                    "type": "string",
                                    "description": "Unique ID for this claim.",
                                },
                                "claim_text": {
                                    "type": "string",
                                    "description": (
                                        "What you found, in natural language "
                                        "(15-800 characters)."
                                    ),
                                },
                                "focus_variables": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Variables involved (1-12).",
                                },
                                "confidence": {
                                    "type": "number",
                                    "description": "Your confidence (0.0-1.0).",
                                },
                                "evidence_basis": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "artifact_id": {"type": "string"},
                                            "rationale": {"type": "string"},
                                        },
                                        "required": ["artifact_id", "rationale"],
                                    },
                                    "description": "Evidence references (1-5).",
                                },
                            },
                            "required": [
                                "claim_id",
                                "claim_text",
                                "focus_variables",
                                "confidence",
                                "evidence_basis",
                            ],
                        },
                        "minItems": 1,
                        "maxItems": 5,
                    }
                },
                "required": ["claims"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------

def build_oi_tool_handler(
    runner: OIEpisodeRunner,
) -> Callable[[str, dict], str]:
    """Build a tool handler closure for OI investigation.

    Returns a function(name, args) -> str suitable for run_with_tools().
    """

    def handler(name: str, args: dict) -> str:
        # Post-submit guard: if already submitted, reject all non-think tools.
        # This handles the case where the LLM emits submit_claims + python_exec
        # in the same response — python_exec must NOT run after scoring.
        if runner.is_submitted and name != "think":
            return json.dumps({
                "error": "Investigation already submitted. No further actions.",
            })

        if name == "think":
            return json.dumps({"status": "noted"})

        elif name == "python_exec":
            code = args.get("code", "")
            if not code:
                return json.dumps({"error": "No code provided."})
            result = runner.run_code(code)
            # Return raw output (matches engine.py pattern)
            return result["output"]

        elif name == "submit_claims":
            return _handle_submit_claims(runner, args)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    return handler


def _handle_submit_claims(runner: OIEpisodeRunner, args: dict) -> str:
    """Parse and submit claims, handling all error cases gracefully."""
    claims_raw = args.get("claims", [])

    if not claims_raw:
        return json.dumps({"error": "No claims provided."})

    # Parse ClaimCards from JSON
    try:
        claims = _parse_claim_cards(claims_raw)
    except (ValueError, TypeError) as e:
        return json.dumps({"error": f"Invalid claim format: {e}"})

    # Submit to runner (may raise on double-submit or validation)
    try:
        runner.submit_claims(claims)
    except RuntimeError as e:
        # Double submission
        return json.dumps({"error": str(e)})
    except ValueError as e:
        # Validation error (too many claims, duplicates, etc.)
        return json.dumps({"error": str(e)})

    # Success — return confirmation (score goes to caller, not solver)
    return json.dumps({
        "status": "submitted",
        "n_claims": len(claims),
        "message": "Claims submitted successfully. Investigation complete.",
    })


def _parse_claim_cards(claims_raw: list[dict]) -> list[ClaimCard]:
    """Parse raw dicts into validated ClaimCard models."""
    cards = []
    for i, raw in enumerate(claims_raw):
        if not isinstance(raw, dict):
            raise TypeError(f"claims[{i}] must be a dict, got {type(raw).__name__}")
        try:
            card = ClaimCard(**raw)
        except Exception as e:
            raise ValueError(f"claims[{i}]: {e}") from e
        cards.append(card)
    return cards


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

@dataclass
class OIInvestigationResult:
    """Result of a complete OI investigation."""

    score: EpisodeScore | EpisodeSubQuestionScore | None = None
    trace: EpisodeTrace = field(default_factory=EpisodeTrace)
    messages: list[dict] = field(default_factory=list)
    n_steps: int = 0
    submitted: bool = False


# ---------------------------------------------------------------------------
# Nudge constants
# ---------------------------------------------------------------------------

_NUDGE_NO_TOOLS = (
    "You have not called any tools. Please use python_exec to analyze "
    "the available data and submit_claims when you have findings."
)

_NUDGE_HALFWAY = (
    "STATUS: You have used {used}/{total} iterations. By now you should have "
    "at least one draft finding with supporting evidence. Stop broad exploration "
    "unless it directly changes a claim you plan to submit."
)

_NUDGE_DEADLINE = (
    "DEADLINE: You have {remaining} iteration(s) left. Submit your supported "
    "claims now. Use remaining iterations only to strengthen or qualify them."
)

_NUDGE_FINAL = (
    "FINAL: This is your LAST iteration. You MUST call submit_claims now "
    "with whatever findings you have. Any analysis is better than no submission."
)

_NUDGE_FORCE_SUBMIT = (
    "You have exhausted all iterations without submitting findings. "
    "You MUST call submit_claims NOW. The ONLY tool available is submit_claims. "
    "Summarize your key findings from the analyses you ran and submit them."
)

_MAX_NUDGES = 2  # Max prose-only nudges before giving up


# ---------------------------------------------------------------------------
# Main driver: real LLM mode
# ---------------------------------------------------------------------------

def run_oi_investigation(
    runner: OIEpisodeRunner,
    client: Any,
    model: str,
    *,
    max_iterations: int = 20,
    temperature: float | None = 0.0,
    max_tokens: int | None = None,
) -> OIInvestigationResult:
    """Run a complete OI investigation with a real LLM.

    Custom Responses API loop with OI-specific control flow:
    - Submit-is-terminal: breaks immediately after successful submission
    - Deadline nudging: warns solver when approaching max iterations
    - Prose-only recovery: if solver responds without tools, nudge to act

    Args:
        runner: The OI episode runner (manages namespace, trace, scoring).
        client: OpenAI-compatible client (Azure, vLLM, etc.).
        model: Model name/ID.
        max_iterations: Max tool-calling rounds.
        temperature: Sampling temperature.
        max_tokens: Max tokens per response.

    Returns:
        OIInvestigationResult with score, trace, and conversation history.
    """
    from sreg.inference.responses_utils import convert_tools_for_responses

    # Build prompt
    ctx = runner.get_solver_prompt_context()
    system_prompt = _build_system(ctx)
    user_prompt = _build_user(ctx)
    resp_tools = convert_tools_for_responses(OI_SOLVER_TOOLS)

    handler = build_oi_tool_handler(runner)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    prev_response_id = None
    nudge_count = 0
    halfway_nudged = False
    deadline_nudged = False
    final_nudged = False

    for iteration in range(max_iterations):
        # Build API call kwargs
        kwargs: dict[str, Any] = {"model": model, "tools": resp_tools}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens

        if prev_response_id is None:
            kwargs["instructions"] = system_prompt
            kwargs["input"] = user_prompt
        else:
            kwargs["previous_response_id"] = prev_response_id
            kwargs["input"] = pending_outputs  # noqa: F821

        # Call LLM
        try:
            response = client.responses.create(**kwargs)
        except Exception as e:
            logger.warning("LLM call failed: %s — retrying without temp/tokens", e)
            kwargs.pop("temperature", None)
            kwargs.pop("max_output_tokens", None)
            # Disable for future iterations so we don't retry every time
            temperature = None
            max_tokens = None
            response = client.responses.create(**kwargs)

        prev_response_id = response.id

        # Parse response output items
        text_content = None
        tool_calls = []
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        text_content = (text_content or "") + part.text
            elif item.type == "function_call":
                tool_calls.append(item)

        # Record assistant message
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": text_content or "",
        }
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

        # No tool calls — nudge or stop
        if not tool_calls:
            if nudge_count < _MAX_NUDGES and not runner.is_submitted:
                nudge_count += 1
                nudge_text = _NUDGE_NO_TOOLS
                messages.append({"role": "user", "content": nudge_text})
                # For Responses API: send nudge as plain input
                pending_outputs = nudge_text
                continue
            break

        # Dispatch tool calls
        pending_outputs = []
        remaining = max_iterations - iteration - 1
        for tc in tool_calls:
            try:
                args = json.loads(tc.arguments)
            except json.JSONDecodeError:
                args = {}

            # Hard guard: on final iteration, reject non-submit calls
            if remaining <= 0 and tc.name != "submit_claims" and tc.name != "think":
                result_str = (
                    "ERROR: No iterations remaining. You MUST call submit_claims "
                    "now. Summarize your findings and submit."
                )
            else:
                result_str = handler(tc.name, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.call_id,
                "content": result_str,
            })
            pending_outputs.append({
                "type": "function_call_output",
                "call_id": tc.call_id,
                "output": result_str,
            })

        # Submit-is-terminal: break immediately after submission
        if runner.is_submitted:
            break

        # Progressive deadline nudges
        remaining = max_iterations - iteration - 1
        used = iteration + 1
        if not runner.is_submitted and remaining > 0:
            pct = used / max_iterations
            if pct >= 0.5 and not halfway_nudged:
                halfway_nudged = True
                nudge = _NUDGE_HALFWAY.format(used=used, total=max_iterations)
                messages.append({"role": "user", "content": nudge})
            elif pct >= 0.75 and not deadline_nudged:
                deadline_nudged = True
                nudge = _NUDGE_DEADLINE.format(remaining=remaining)
                messages.append({"role": "user", "content": nudge})
            elif remaining == 1 and not final_nudged:
                final_nudged = True
                messages.append({"role": "user", "content": _NUDGE_FINAL})

    # ------------------------------------------------------------------
    # Force-submit: if solver never submitted, give it one last chance
    # with ONLY submit_claims available (no python_exec, no think).
    # ------------------------------------------------------------------
    if not runner.is_submitted:
        logger.warning("Solver exhausted iterations without submitting — forcing submit round")
        submit_tool = next(t for t in OI_SOLVER_TOOLS if t["function"]["name"] == "submit_claims")
        submit_only_tools = convert_tools_for_responses([submit_tool])

        messages.append({"role": "user", "content": _NUDGE_FORCE_SUBMIT})

        # Build input: include pending tool outputs so the API chain is valid
        force_input: list[dict[str, Any]] = []
        if isinstance(pending_outputs, list):
            force_input.extend(pending_outputs)
        force_input.append({"role": "user", "content": _NUDGE_FORCE_SUBMIT})

        force_kwargs: dict[str, Any] = {
            "model": model,
            "tools": submit_only_tools,
            "previous_response_id": prev_response_id,
            "input": force_input,
        }
        force_resp = None
        try:
            force_resp = client.responses.create(**force_kwargs)
        except Exception as e:
            logger.warning("Force-submit with prev_id failed: %s — retrying standalone", e)
            # Fallback: standalone call with summary context (no tool_calls)
            # Extract solver reasoning from assistant text messages
            solver_notes = []
            for m in messages:
                if m.get("role") == "assistant" and m.get("content"):
                    solver_notes.append(m["content"])
            summary = "\n---\n".join(solver_notes[-5:]) if solver_notes else "(no notes)"
            standalone_input = (
                f"You investigated a research case. Here are your recent notes:\n\n"
                f"{summary}\n\n{_NUDGE_FORCE_SUBMIT}"
            )
            try:
                force_resp = client.responses.create(
                    model=model,
                    tools=submit_only_tools,
                    instructions=system_prompt,
                    input=standalone_input,
                )
            except Exception as e2:
                logger.warning("Force-submit standalone also failed: %s", e2)

        if force_resp is not None:
            prev_response_id = force_resp.id
            for item in force_resp.output:
                if item.type == "function_call":
                    try:
                        args = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning("Force-submit returned malformed arguments: %s", e)
                        continue
                    result_str = handler(item.name, args)
                    messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [{
                            "id": item.call_id,
                            "type": "function",
                            "function": {"name": item.name, "arguments": item.arguments},
                        }],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": item.call_id,
                        "content": result_str,
                    })

    return OIInvestigationResult(
        score=runner.get_sq_score() or runner.get_score(),
        trace=runner.get_trace(),
        messages=messages,
        n_steps=runner._step["current"],
        submitted=runner.is_submitted,
    )


# ---------------------------------------------------------------------------
# Scripted driver: for testing without LLM
# ---------------------------------------------------------------------------

@dataclass
class ScriptedAction:
    """A predetermined solver action for testing.

    tool: "python_exec", "think", "submit_claims", or None (no action = stop).
    args: Arguments dict for the tool call.
    """

    tool: str | None
    args: dict = field(default_factory=dict)


def run_oi_scripted(
    runner: OIEpisodeRunner,
    script: list[ScriptedAction],
) -> OIInvestigationResult:
    """Run an OI investigation with a predetermined script.

    For testing the driver loop without an LLM. The script specifies
    what tool calls the "solver" makes at each step.

    Args:
        runner: The OI episode runner.
        script: List of predetermined actions.

    Returns:
        OIInvestigationResult.
    """
    handler = build_oi_tool_handler(runner)
    messages: list[dict] = []

    ctx = runner.get_solver_prompt_context()
    messages.append({"role": "system", "content": _build_system(ctx)})
    messages.append({"role": "user", "content": _build_user(ctx)})

    for i, action in enumerate(script):
        if action.tool is None:
            # Solver chose to stop without acting
            messages.append({"role": "assistant", "content": "Investigation complete."})
            break

        # Simulate the tool call
        call_id = f"call_{i}"
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {
                    "name": action.tool,
                    "arguments": json.dumps(action.args),
                },
            }],
        })

        # Dispatch
        result = handler(action.tool, action.args)
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": result,
        })

        if runner.is_submitted:
            break

    return OIInvestigationResult(
        score=runner.get_sq_score() or runner.get_score(),
        trace=runner.get_trace(),
        messages=messages,
        n_steps=runner._step["current"],
        submitted=runner.is_submitted,
    )


# ---------------------------------------------------------------------------
# Prompt building helpers
# ---------------------------------------------------------------------------

def _build_system(ctx: dict) -> str:
    """Build system prompt from runner context."""
    parts = [build_oi_system_prompt()]
    if ctx.get("title"):
        title_line = f"\n\n## Investigation: {ctx['title']}"
        if ctx.get("domain"):
            title_line += f" ({ctx['domain']})"
        parts.append(title_line)
    parts.append("\n\n" + build_oi_tools_section(ctx["artifact_catalog"]))
    return "".join(parts)


def _build_user(ctx: dict) -> str:
    """Build user prompt from runner context."""
    return (
        build_oi_briefing(ctx["research_brief"], ctx["artifact_catalog"])
        + "\n\n"
        + build_oi_strategy_section()
    )


__all__ = [
    "OI_SOLVER_TOOLS",
    "OIInvestigationResult",
    "ScriptedAction",
    "build_oi_tool_handler",
    "run_oi_investigation",
    "run_oi_scripted",
]
