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
from sreg.tools.oi_runner import OIEpisodeRunner, SubmissionCancelled

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
    except RuntimeError as e:
        # Race recovery: a previous call's worker thread may have committed
        # the runner AFTER that call's timeout returned an error to the
        # agent. In that case, the current retry's `runner.submit_claims`
        # sees `_submitted=True` and raises "already submitted". Rather
        # than losing the episode, reuse the score that is already on the
        # runner. This is the complement of `cancel_event`: the event
        # closes most of the race window, this handles the residual case
        # where the thread committed before we could signal cancellation.
        if (
            "already submitted" in str(e)
            and runner.is_submitted
            and runner.get_score() is not None
        ):
            recovered = runner.get_score()
            state["score"] = recovered
            state["submitted"] = True
            state["submit_error"] = None
            logger.warning(
                "submit_claims retry recovered score from background-committed "
                "runner (previous timeout's worker finished after env gave up)"
            )
            return (
                f"Claims submitted successfully (recovered from background "
                f"scoring). Correctness: {recovered.correctness:.3f}, "
                f"Coverage: {recovered.weighted_coverage:.3f}, "
                f"Total: {recovered.total:.3f}"
            )
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
