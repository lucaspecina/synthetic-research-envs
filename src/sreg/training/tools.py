"""Async tool functions for the verifiers environment.

These functions are registered as tools in SregEnv. The model calls them
via tool_calls; verifiers dispatches to them and returns the result as
a ToolMessage.

Hidden args (runner, state) are injected by StatefulToolEnv.update_tool_args()
and are NOT visible in the tool schema shown to the model.

NOTE: The `distribution` parameter on submit() is typed as `str` (JSON string)
rather than `dict[str, float]` because the openai-agents strict schema validator
rejects `additionalProperties` on object types. The model passes a JSON string
like '{"low": 0.3, "high": 0.7}' and we parse it here.
"""

from __future__ import annotations

import json

from sreg.agent.python_exec import execute_code as _exec_code_sync
from sreg.env.episode import EpisodeRunner
from sreg.models.episode import ActionDef
from sreg.training.adapters import (
    action_id_is_intervene,
    make_intervene_action,
    make_observe_action,
    step_result_to_text,
)
from sreg.training.types import SubmitPayload
from sreg.training.validators import validate_submit_payload


async def research_action(
    action_id: str,
    runner: EpisodeRunner | None = None,
    state: dict | None = None,
) -> str:
    """Execute a research action from the available list.

    Each action has a cost in budget units and returns findings about
    the variables under study.

    Args:
        action_id: ID of the action to execute (e.g. 'obs_temperature').
    """
    if runner is None or state is None:
        return "Error: environment not initialized."

    if runner.is_finished:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "research_action",
                "action_id": action_id,
                "ok": False,
                "error": "episode already finished",
            }
        )
        return "Error: episode already finished. Use submit to end."

    # Determine action type from action_defs
    action_defs: list[ActionDef] = list(runner.episode.action_defs)
    try:
        if action_id_is_intervene(action_id, action_defs):
            action = make_intervene_action(action_id)
        else:
            action = make_observe_action(action_id)
        result = runner.step(action)
    except (ValueError, RuntimeError) as e:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "research_action",
                "action_id": action_id,
                "ok": False,
                "error": str(e),
            }
        )
        return f"Error: {e}"

    state["budget_used"] = runner.episode.budget - runner.budget_remaining
    state["tool_trace"].append(
        {
            "tool": "research_action",
            "action_id": action_id,
            "ok": True,
        }
    )

    # Sync observations into python_exec namespace
    ns = state.get("python_namespace")
    if ns is not None:
        ns["observations"] = dict(runner.evidence)

    return step_result_to_text(result)


async def submit(
    choice: str | None = None,
    distribution: str | None = None,
    adjustment_set: list[str] | None = None,
    runner: EpisodeRunner | None = None,
    state: dict | None = None,
) -> str:
    """Submit your final answer to the research question.

    Provide exactly ONE of the following, depending on the question type:
    - choice: for questions asking you to pick an option (e.g. "A", "yes", "temperature")
    - distribution: JSON string with a probability distribution (e.g. '{"low": 0.3, "high": 0.7}')
    - adjustment_set: for questions asking which variables to control for (e.g. ["age", "income"])

    Args:
        choice: Single choice answer.
        distribution: JSON string mapping target states to probabilities.
        adjustment_set: List of variable names.
    """
    if state is None:
        return "Error: environment not initialized."

    if state.get("submitted", False):
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "submit",
                "ok": False,
                "error": "already submitted",
            }
        )
        return "Error: you already submitted an answer."

    # Parse distribution from JSON string if provided
    dist_dict: dict[str, float] | None = None
    if distribution is not None:
        try:
            dist_dict = json.loads(distribution)
            if not isinstance(dist_dict, dict):
                state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
                state["tool_trace"].append(
                    {
                        "tool": "submit",
                        "ok": False,
                        "error": "distribution is not a JSON object",
                    }
                )
                return "Error: distribution must be a JSON object mapping states to probabilities."
        except (json.JSONDecodeError, TypeError) as e:
            state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
            state["tool_trace"].append(
                {
                    "tool": "submit",
                    "ok": False,
                    "error": f"invalid distribution JSON: {e}",
                }
            )
            return f"Error: invalid distribution JSON: {e}"

    payload = SubmitPayload(
        choice=choice,
        distribution=dist_dict,
        adjustment_set=adjustment_set,
    )

    eval_type = state.get("eval_type", "")
    try:
        validate_submit_payload(payload, eval_type)
    except ValueError as e:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1
        state["tool_trace"].append(
            {
                "tool": "submit",
                "ok": False,
                "error": str(e),
            }
        )
        return f"Error: {e}"

    # Mark as submitted — scoring happens in the rubric
    state["submitted"] = True
    state["submission_payload"] = payload.model_dump()
    state["done_reason"] = "submit"
    state["tool_trace"].append(
        {
            "tool": "submit",
            "ok": True,
        }
    )

    return "Answer submitted. The episode is now complete."


# ── python_exec: delegates to shared kernel in agent/python_exec.py ──


async def python_exec(
    code: str,
    state: dict | None = None,
) -> str:
    """Execute Python code in a persistent interpreter.

    Variables, imports, and data persist between calls within the same
    episode (like a Jupyter notebook). The observations from research_action
    calls are available as the `observations` dict.

    Pre-loaded in the namespace: numpy (np), pandas (pd), scipy, math,
    statistics, json, collections, itertools, functools, re.
    Datasets from the research case are available as `df` (if provided).

    Uses the shared kernel from agent/python_exec.py to ensure identical
    semantics between diagnostic solving and RL training.

    Args:
        code: Python code to execute.
    """
    if state is None:
        return "Error: environment not initialized."

    namespace = state.get("python_namespace")
    if namespace is None:
        return "Error: python interpreter not initialized."

    # Delegate to shared kernel
    result = _exec_code_sync(code, namespace)

    # Track in state (verifiers needs this for metrics)
    exec_count = state.get("python_exec_count", 0) + 1
    state["python_exec_count"] = exec_count

    if not result.ok:
        state["invalid_action_count"] = state.get("invalid_action_count", 0) + 1

    state["tool_trace"].append(
        {
            "tool": "python_exec",
            "ok": result.ok,
            "exec_count": exec_count,
            "truncated": result.truncated,
        }
    )

    return result.output
