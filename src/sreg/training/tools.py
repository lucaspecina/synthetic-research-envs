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

from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.tools.oi_runner import OIEpisodeRunner

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
    try:
        score = await asyncio.wait_for(
            asyncio.to_thread(runner.submit_claims, claim_cards),
            timeout=_SCORING_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        state["submit_error"] = "scoring_timeout"
        logger.error("submit_claims scoring timed out after %.0fs", _SCORING_TIMEOUT_S)
        return f"Error: scoring timed out after {_SCORING_TIMEOUT_S:.0f}s."
    except ValueError as e:
        state["submit_error"] = f"validation_error: {e}"
        logger.warning("submit_claims validation error: %s", e)
        return f"Submission error: {e}"
    except RuntimeError as e:
        state["submit_error"] = f"runtime_error: {e}"
        logger.error("submit_claims runtime error: %s", e)
        return f"Error: {e}"

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
