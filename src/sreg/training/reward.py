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


def python_exec_calls_metric(state: dict, **kwargs) -> float:
    """Track python_exec tool usage. Agents that never analyze data are suspect."""
    return float(state.get("python_exec_calls", 0))


def think_calls_metric(state: dict, **kwargs) -> float:
    """Track think tool usage. Signals reasoning vs direct tool spam."""
    return float(state.get("think_calls", 0))


def submit_attempts_metric(state: dict, **kwargs) -> float:
    """Track how many times the agent called submit_claims. >1 means a retry
    happened (parse/validation/timeout/cancelled → agent tried again)."""
    return float(state.get("submit_attempts", 0))


def submit_error_metric(state: dict, **kwargs) -> float:
    """Track whether a submit error occurred (1.0) or not (0.0)."""
    return 1.0 if state.get("submit_error") else 0.0


def recovery_used_metric(state: dict, **kwargs) -> float:
    """Track whether the fingerprint recovery path fired (1.0) or not (0.0).
    A non-zero value signals async race pressure in the env bridge — useful
    for spotting Azure slowdowns that trigger timeout + race recovery."""
    return 1.0 if state.get("recovery_used") else 0.0


def scoring_wall_clock_metric(state: dict, **kwargs) -> float:
    """Track total scoring (submit_claims) wall-clock seconds. Watch the tail
    for Azure rate-limit pressure or compiler/judge slowdowns."""
    return float(state.get("scoring_wall_clock_s", 0.0))
