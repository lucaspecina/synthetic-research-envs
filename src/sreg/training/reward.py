"""Reward functions for SregEnv training.

Terminal-only reward: score.total on successful submit, penalties otherwise.
The submit_claims tool stores the score in state — reward reads from there.
No re-computation, no double-submit.

Metrics (weight=0) track diagnostics without affecting reward.
"""

from __future__ import annotations


def terminal_reward(state: dict, **kwargs) -> float:
    """Terminal reward from SREG scoring pipeline.

    Returns score.total (0.0-1.0) on successful submit.
    Penalties for failure modes:
      -0.05: tried to submit but validation/scoring failed
      -0.10: never attempted to submit (max turns or no tool calls)
    """
    if state.get("submitted"):
        score = state.get("score")
        if score is not None:
            return float(score.total)
        return 0.0

    # Not submitted — penalty by failure mode
    if state.get("submit_error"):
        return -0.05  # tried but failed
    return -0.10  # didn't even try


def submitted_metric(state: dict, **kwargs) -> float:
    """Track whether the agent submitted (1.0) or not (0.0)."""
    return 1.0 if state.get("submitted", False) else 0.0


def step_count_metric(state: dict, **kwargs) -> float:
    """Track number of tool calls made during the episode."""
    return float(state.get("step_count", 0))


def submit_error_metric(state: dict, **kwargs) -> float:
    """Track whether a submit error occurred (1.0) or not (0.0)."""
    return 1.0 if state.get("submit_error") else 0.0
