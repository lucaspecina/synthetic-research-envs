"""Tool functions for the SregEnv training environment.

These are registered as tools in SregEnv via verifiers' add_tool.
Hidden args (runner, state) are injected by update_tool_args and
are NOT visible in the tool schema shown to the model.

The tool surface mirrors the OI driver (oi_driver.py):
  python_exec — persistent Python interpreter
  think       — scratchpad (no side effects)
  submit_claims — submit findings, triggers scoring
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading

from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.tools.oi_runner import (
    AlreadySubmittedError,
    OIEpisodeRunner,
    SubmissionCancelled,
)

logger = logging.getLogger(__name__)

# Timeout for submit_claims scoring. Includes 2 LLM calls (compiler + judge),
# each of which can be slow under concurrent rollout load. 300s is generous;
# a healthy run completes in ~5-10s, timeout is a safety net, not a target.
_SCORING_TIMEOUT_S = 300.0


async def python_exec(
    code: str,
    runner: OIEpisodeRunner | None = None,
    state: dict | None = None,
) -> str:
    """Execute Python code in a persistent interpreter.

    Variables persist between calls (like a Jupyter notebook).
    Pre-loaded: numpy (np), pandas (pd), scipy, math, statistics.
    Use load_artifact(id) to load datasets, save_artifact(df, label)
    to save derived data.

    Args:
        code: Python code to execute.
    """
    if runner is None or state is None:
        return "Error: environment not initialized."

    # Run in thread to avoid blocking the event loop during concurrent rollouts.
    # User code can be slow (regression, stats) — don't starve other rollouts.
    result = await asyncio.to_thread(runner.run_code, code)
    state["step_count"] = state.get("step_count", 0) + 1

    output = result.get("output", "")
    return output if output else "(no output)"


async def think(
    reasoning: str,
    state: dict | None = None,
) -> str:
    """Think through your reasoning step by step.

    Your reasoning will be recorded but has no side effects.

    Args:
        reasoning: Your step-by-step reasoning.
    """
    if state is None:
        return "Error: environment not initialized."

    state["step_count"] = state.get("step_count", 0) + 1
    return "Reasoning recorded."


async def submit_claims(
    claims: list,
    runner: OIEpisodeRunner | None = None,
    state: dict | None = None,
) -> str:
    """Submit your research findings as atomic claim cards.

    Call ONCE at the end of your investigation. 1-15 claims.

    Args:
        claims: List of claim objects with claim_id, claim_text,
                focus_variables, confidence, and evidence_basis.
    """
    if runner is None or state is None:
        return "Error: environment not initialized."

    # Count the tool call regardless of outcome (matches python_exec / think).
    # Reward diagnostics and any per-step penalty need this to be accurate.
    state["step_count"] = state.get("step_count", 0) + 1

    if state.get("submitted"):
        return "Error: you already submitted claims."

    # Parse claim dicts into ClaimCards
    try:
        claim_cards = [_parse_claim(c) for c in claims]
    except Exception as e:
        state["submit_error"] = f"parse_error: {e}"
        logger.warning("submit_claims parse error: %s", e)
        return f"Error parsing claims: {e}"

    # Score via runner (compile + verify + judge). This makes LLM calls
    # (compiler + relevance judge) and can take seconds. Run in thread
    # to avoid blocking the event loop.
    #
    # `cancel_event` closes the race described in issue #25: asyncio.wait_for
    # cancels the await but NOT the worker thread. Without the event, the
    # thread can still commit the score AFTER we have already returned a
    # timeout to the agent, leaving runner._submitted=True — the next retry
    # would fail with "already submitted" and the episode would be lost.
    # With the event, the thread checks it at the commit checkpoint and
    # raises SubmissionCancelled instead of committing.
    cancel_event = threading.Event()
    try:
        score = await asyncio.wait_for(
            asyncio.to_thread(
                runner.submit_claims, claim_cards, cancel_event=cancel_event,
            ),
            timeout=_SCORING_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        # Signal the worker thread to abort its commit. It cannot be killed
        # but it will honor the event at its next checkpoint.
        cancel_event.set()
        state["submit_error"] = "scoring_timeout"
        logger.error(
            "submit_claims scoring timed out after %.0fs; cancel_event set",
            _SCORING_TIMEOUT_S,
        )
        return f"Error: scoring timed out after {_SCORING_TIMEOUT_S:.0f}s."
    except ValueError as e:
        state["submit_error"] = f"validation_error: {e}"
        logger.warning("submit_claims validation error: %s", e)
        return f"Submission error: {e}"
    except AlreadySubmittedError as e:
        # Race recovery: a previous call's worker thread may have committed
        # the runner AFTER that call's timeout returned an error to the
        # agent. In that case, the current retry's `runner.submit_claims`
        # sees `_submitted=True` and raises AlreadySubmittedError. Rather
        # than losing the episode, reuse the score that is already on the
        # runner — but ONLY if the retry's claims match the payload that
        # actually committed. Otherwise we would silently award an old
        # score to a modified retry, which is a correctness bug masquerading
        # as recovery (Codex review finding, 2026-04-15).
        recovered = runner.get_score()
        if recovered is not None and _claims_match(claim_cards, e.last_claims):
            state["score"] = recovered
            state["submitted"] = True
            state["submit_error"] = None
            logger.warning(
                "submit_claims retry recovered score from background-committed "
                "runner (previous timeout's worker finished after env gave up); "
                "claim payloads matched."
            )
            return (
                f"Claims submitted successfully (recovered from background "
                f"scoring). Correctness: {recovered.correctness:.3f}, "
                f"Coverage: {recovered.weighted_coverage:.3f}, "
                f"Total: {recovered.total:.3f}"
            )
        # Either no score on the runner (shouldn't happen if _submitted=True
        # but defensive) OR the retry sent different claims. Do NOT silently
        # recover; surface it so the agent/operator can see what happened.
        state["submit_error"] = "already_submitted_payload_mismatch"
        logger.error(
            "submit_claims AlreadySubmittedError with claim mismatch: "
            "retry sent %d claims, runner committed %d. Refusing silent recovery.",
            len(claim_cards), len(e.last_claims),
        )
        return (
            "Error: an earlier submission already committed with different "
            "claims; cannot silently attribute that score to this retry."
        )
    except RuntimeError as e:
        state["submit_error"] = f"runtime_error: {e}"
        logger.error("submit_claims runtime error: %s", e)
        return f"Error: {e}"
    except SubmissionCancelled as e:
        # Rare: can only reach here if cancel_event was set externally
        # BEFORE wait_for fired its TimeoutError. Defensive handler — the
        # contract is that the runner stays pristine, so treat as cancelled.
        state["submit_error"] = "cancelled"
        logger.warning("submit_claims cancelled (pre-timeout signal): %s", e)
        return f"Error: submission cancelled: {e}"

    # Store score in state — reward function reads from here
    state["score"] = score
    state["submitted"] = True
    state["submit_error"] = None

    return (
        f"Claims submitted successfully. "
        f"Correctness: {score.correctness:.3f}, "
        f"Coverage: {score.weighted_coverage:.3f}, "
        f"Total: {score.total:.3f}"
    )


def _parse_claim(d: dict) -> ClaimCard:
    """Parse a raw claim dict (from model tool call) into a ClaimCard."""
    evidence = []
    for ref in d.get("evidence_basis", []):
        evidence.append(EvidenceRef(
            artifact_id=ref["artifact_id"],
            rationale=ref.get("rationale", ""),
        ))

    return ClaimCard(
        claim_id=d["claim_id"],
        claim_text=d["claim_text"],
        focus_variables=d.get("focus_variables", []),
        confidence=d.get("confidence", 0.5),
        evidence_basis=evidence,
    )


def _claims_match(a: list[ClaimCard], b: list[ClaimCard]) -> bool:
    """Check if two claim payloads are equivalent for recovery purposes.

    Used by the AlreadySubmittedError handler to decide whether a retry's
    claims match the claims that actually committed in the background.
    Full pydantic equality (claim_id + text + focus_variables + confidence
    + evidence_basis) — anything less would let a modified retry silently
    inherit an old score.
    """
    if len(a) != len(b):
        return False
    # Order matters: the runner stores claims in submit order, and the
    # compiler/judge ran on that order. A reordered retry should not
    # implicitly match.
    return all(ac == bc for ac, bc in zip(a, b))
