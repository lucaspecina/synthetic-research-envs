"""Adapter layer: translates between verifiers tool args and SREG models.

This module is the bridge between the verifiers framework (tool call strings,
state dicts) and SREG's pydantic models (Action, StepResult, etc.).
"""

from __future__ import annotations

from sreg.models.episode import Action, ActionType, StepResult
from sreg.training.types import (
    CHOICE_EVAL_TYPES,
    DISTRIBUTION_EVAL_TYPES,
    SET_EVAL_TYPES,
    SubmitPayload,
)


def make_observe_action(action_id: str) -> Action:
    """Create an SREG Action for observing/intervening via action_id."""
    return Action(type=ActionType.OBSERVE, action_id=action_id)


def make_intervene_action(action_id: str) -> Action:
    """Create an SREG Action for an intervention via action_id."""
    return Action(type=ActionType.INTERVENE, action_id=action_id)


def make_submit_action(payload: SubmitPayload, eval_type: str) -> Action:
    """Create an SREG submit Action from a SubmitPayload.

    For distribution types, the answer maps directly to Action.answer.
    For choice/set types, we create a dummy answer dict to satisfy
    Action validation — scoring reads from SubmitPayload, not Action.
    """
    answer = extract_answer(payload, eval_type)
    if isinstance(answer, dict):
        return Action(type=ActionType.SUBMIT, answer=answer)
    # Choice/set types: dummy answer for Action validation.
    # The real answer lives in SubmitPayload (stored in env state).
    # Scoring always reads from SubmitPayload, never from Action.
    return Action(type=ActionType.SUBMIT, answer={"_submitted": 1.0})


def extract_answer(payload: SubmitPayload, eval_type: str) -> dict[str, float] | str | list[str]:
    """Extract the answer value from a SubmitPayload based on eval type."""
    if eval_type in DISTRIBUTION_EVAL_TYPES:
        if payload.distribution is None:
            raise ValueError(f"Eval type '{eval_type}' requires distribution")
        return payload.distribution

    if eval_type in CHOICE_EVAL_TYPES:
        if payload.choice is None:
            raise ValueError(f"Eval type '{eval_type}' requires choice")
        return payload.choice

    if eval_type in SET_EVAL_TYPES:
        if payload.adjustment_set is None:
            raise ValueError(f"Eval type '{eval_type}' requires adjustment_set")
        return payload.adjustment_set

    raise ValueError(f"Unknown eval type: '{eval_type}'")


def step_result_to_text(result: StepResult) -> str:
    """Convert a StepResult to agent-visible text.

    Only exposes what the agent should see — no hidden BN details.
    """
    parts: list[str] = []

    if result.observation:
        parts.append(result.observation.description)

    for extra in result.extra_observations:
        parts.append(extra.description)

    if result.distribution:
        dist_str = ", ".join(f"{k}: {v:.4f}" for k, v in result.distribution.items())
        parts.append(f"Distribution: {{{dist_str}}}")

    if not parts:
        # Submit or unknown action — generic confirmation
        parts.append("Action processed.")

    parts.append(f"Budget remaining: {result.remaining_budget}")

    return "\n".join(parts)


def action_id_is_intervene(action_id: str, action_defs: list) -> bool:
    """Check if an action_id refers to an intervene action.

    Args:
        action_id: The action ID to check.
        action_defs: List of ActionDef objects from the episode.
    """
    for adef in action_defs:
        if adef.id == action_id:
            return adef.action_type == "intervene"
    return False
