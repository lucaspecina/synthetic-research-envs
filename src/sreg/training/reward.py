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


# ---------------------------------------------------------------------------
# Per-category error metrics
#
# These complement submit_error_metric by exposing WHICH error type fired,
# not just whether one did. Binary metrics rather than a single categorical
# because verifiers' rubric metrics are scalar floats. Aggregated across a
# batch, each gives a rate (fraction of rollouts with that failure mode) —
# which is exactly the observability signal we need for diagnosing training
# runs without re-executing rollouts (Codex review 2026-04-15).
# ---------------------------------------------------------------------------


def _is_category(state: dict, target: str) -> float:
    return 1.0 if state.get("submit_error_category") == target else 0.0


def timeout_rate_metric(state: dict, **kwargs) -> float:
    """1.0 if submit_claims hit the async scoring timeout. Rising timeout
    rate across a batch signals Azure rate-limit pressure or overload."""
    return _is_category(state, "timeout")


def payload_mismatch_rate_metric(state: dict, **kwargs) -> float:
    """1.0 if the fingerprint recovery refused to attribute an old score
    to a modified retry. Rare if healthy; non-zero warrants investigation
    (agent retrying with changed claims after a timeout)."""
    return _is_category(state, "payload_mismatch")


def validation_error_rate_metric(state: dict, **kwargs) -> float:
    """1.0 if the runner rejected claims (bad evidence_basis, duplicate
    claim_ids, claim_cap exceeded, etc). High rate signals a prompt
    engineering problem — the agent doesn't understand the contract."""
    return _is_category(state, "validation_error")


def parse_error_rate_metric(state: dict, **kwargs) -> float:
    """1.0 if the tool args couldn't be coerced into ClaimCards. High
    rate signals a schema problem — the agent produces malformed tool
    calls (missing fields, wrong types, etc)."""
    return _is_category(state, "parse_error")


def runtime_error_rate_metric(state: dict, **kwargs) -> float:
    """1.0 if a non-validation RuntimeError bubbled out of the runner.
    Should be near-zero in a healthy stack; non-zero means unexpected
    runner-side failure (LLM client error, compiler crash, etc)."""
    return _is_category(state, "runtime_error")


def cancelled_rate_metric(state: dict, **kwargs) -> float:
    """1.0 if submit_claims was cancelled via cancel_event before the
    async timeout (rare — external cancellation signal)."""
    return _is_category(state, "cancelled")


def recovery_used_metric(state: dict, **kwargs) -> float:
    """Track whether the fingerprint recovery path fired (1.0) or not (0.0).
    A non-zero value signals async race pressure in the env bridge — useful
    for spotting Azure slowdowns that trigger timeout + race recovery."""
    return 1.0 if state.get("recovery_used") else 0.0


def scoring_wall_clock_metric(state: dict, **kwargs) -> float:
    """Track total scoring (submit_claims) wall-clock seconds. Watch the tail
    for Azure rate-limit pressure or compiler/judge slowdowns."""
    return float(state.get("scoring_wall_clock_s", 0.0))
