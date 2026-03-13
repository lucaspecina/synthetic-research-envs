"""Reward computation for RL training.

Dispatches to the correct VerifierTool scorer based on eval_type.
Designed to be used as reward functions in a verifiers Rubric, but
the core logic (score_submission) is framework-agnostic.

NOTE: This is the SINGLE authority for reward computation in training.
The verifiers Rubric reads from this module. EpisodeRunner does NOT
compute rewards — it only manages the interaction loop.
"""

from __future__ import annotations

import math

from sreg.models.task import TaskType
from sreg.tools.verifier import VerifierTool
from sreg.training.types import (
    CHOICE_EVAL_TYPES,
    DISTRIBUTION_EVAL_TYPES,
    SET_EVAL_TYPES,
    SubmitPayload,
)

_verifier = VerifierTool()

# Default KL cutoff for reward conversion. Provisional — should be
# calibrated from empirical KL histograms of generated SRCs.
DEFAULT_KL_CUTOFF = 5.0


def score_submission(
    payload: SubmitPayload,
    eval_type: str,
    correct_answer: dict,
    task_metadata: dict | None = None,
    kl_cutoff: float = DEFAULT_KL_CUTOFF,
) -> float:
    """Score an agent submission against ground truth.

    Returns a float in [0.0, 1.0] where 1.0 = perfect.

    Args:
        payload: The agent's submitted answer.
        eval_type: One of the 9 eval types.
        correct_answer: The ground truth from Task.correct_answer.
        task_metadata: Optional extra data (hypotheses, intervention, etc.)
        kl_cutoff: Max KL for distribution scoring (configurable).
    """
    task_metadata = task_metadata or {}

    if eval_type in DISTRIBUTION_EVAL_TYPES:
        return _score_distribution(payload, correct_answer, kl_cutoff)

    if eval_type in CHOICE_EVAL_TYPES:
        return _score_choice(payload, eval_type, correct_answer, task_metadata)

    if eval_type in SET_EVAL_TYPES:
        return _score_set(payload, correct_answer)

    raise ValueError(f"Unknown eval type: '{eval_type}'")


def _score_distribution(
    payload: SubmitPayload,
    correct_answer: dict[str, float],
    kl_cutoff: float = DEFAULT_KL_CUTOFF,
) -> float:
    """Score distribution-type answers (infer_target, causal_effect, infer_latent_cause).

    Uses KL divergence, converted to a [0, 1] reward.
    Linear mapping: reward = max(0, 1 - KL / kl_cutoff).
    """
    if payload.distribution is None:
        return 0.0

    # Filter out NaN/inf values
    clean_dist = {
        k: v
        for k, v in payload.distribution.items()
        if isinstance(v, (int, float)) and math.isfinite(v)
    }
    if not clean_dist:
        return 0.0

    kl = _verifier.kl_divergence(clean_dist, correct_answer)
    return max(0.0, 1.0 - kl / kl_cutoff)


def _score_choice(
    payload: SubmitPayload,
    eval_type: str,
    correct_answer: dict,
    task_metadata: dict,
) -> float:
    """Score choice-type answers."""
    if payload.choice is None:
        return 0.0

    choice = payload.choice.strip()

    if eval_type == TaskType.HYPOTHESIS_SELECTION:
        return _verifier.score_hypothesis(choice, correct_answer)

    if eval_type == TaskType.NEXT_BEST_OBSERVATION:
        return _verifier.score_nbo(choice, correct_answer)

    if eval_type == TaskType.BEST_INTERVENTION:
        # Agent submits "node:state" as choice
        if ":" in choice:
            node, state = choice.split(":", 1)
            return _verifier.score_best_intervention(node, state, correct_answer)
        return 0.0

    if eval_type == TaskType.COMPARE_INTERVENTIONS:
        return _verifier.score_compare_interventions(choice, correct_answer)

    if eval_type == TaskType.SHOULD_CONDITION:
        return _verifier.score_should_condition(choice, correct_answer)

    return 0.0


def _score_set(payload: SubmitPayload, correct_answer: dict[str, float]) -> float:
    """Score set-type answers (adjustment_set)."""
    if payload.adjustment_set is None:
        return 0.0
    return _verifier.score_adjustment_set(payload.adjustment_set, correct_answer)
