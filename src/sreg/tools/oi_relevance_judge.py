"""LLM relevance judge: pairwise claim x SQ -> relevance score.

Primary scorer for relevance in the SQ v2 pipeline.  Replaces
compute_structural_relevance (DAG heuristics) and assertion_compat
(teacher Assertion matching) with a single LLM call per claim-SQ pair.

Design decisions (consensus Claude/Codex/Cursor 2026-04-01):
- Pairwise: one claim x one SQ -> relevance 0..1
- Consumes render_answer_key() views, NOT verdict.detail directly
- Does NOT see the teacher's Assertion (it's compiler hypothesis, not truth)
- Brief as weak context (disambiguate, not dominate)
- Labels derived post-hoc from score, not by the LLM
- For RL migration: replace this module with deterministic features or
  distilled classifier when we have enough labeled data

References: scoring_relevance_design.md, a27_answer_key_contract.md
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a scientific relevance judge. Your job is to assess whether a
researcher's finding is relevant to a specific sub-question from a
research brief.

IMPORTANT DISTINCTIONS:
- "Relevant" means the finding ADDRESSES the sub-question — it provides
  information that helps answer it, even partially or indirectly.
- A finding can be TRUE but IRRELEVANT (correct fact, wrong question).
- A finding can be RELEVANT but only PARTIALLY (addresses part of the SQ).
- Focus on SEMANTIC relevance, not surface-level keyword matching.
- Do NOT judge correctness — relevance is independent of whether the claim
  agrees with or contradicts the answer key.
- The brief is weak context; if it conflicts with the SQ, prioritize the SQ.
- Ignore the SQ priority/tier — it does not affect relevance.

SCORING GUIDE:
- 0.9-1.0: Directly answers the core of the sub-question
- 0.7-0.8: Clearly relevant, addresses a major aspect
- 0.4-0.6: Tangentially relevant — related topic, partial overlap
- 0.1-0.3: Weakly relevant — same domain but different question
- 0.0: Completely irrelevant — no meaningful connection

Respond in JSON:
{"relevance": <float 0.0-1.0>, "reasoning": "<1-2 sentences>"}
"""

def _build_user_prompt(
    brief: str,
    sq_text: str,
    sq_focus_vars: str,
    sq_tier: str,
    sq_answer_keys_section: str,
    claim_text: str,
    claim_specs_section: str,
) -> str:
    """Build user prompt via concatenation (safe with arbitrary user strings)."""
    parts = [
        "## Research Brief (context)",
        brief or "(no brief provided)",
        "",
        "## Sub-Question (what we're evaluating against)",
        f"Text: {sq_text}",
        f"Focus variables: {sq_focus_vars}",
        f"Priority: {sq_tier}",
    ]
    if sq_answer_keys_section:
        parts.append(sq_answer_keys_section)
    parts += [
        "",
        "## Claim (the finding to evaluate)",
        f"Text: {claim_text}",
    ]
    if claim_specs_section:
        parts.append(claim_specs_section)
    parts += [
        "",
        "## Task",
        "Rate the relevance of this claim to the sub-question (0.0 to 1.0).",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Core judge function
# ---------------------------------------------------------------------------


def judge_relevance(
    claim_text: str,
    sq_text: str,
    sq_focus_variables: tuple[str, ...],
    sq_tier: str,
    sq_answer_keys: list[dict[str, Any]],
    brief_text: str,
    llm_call: Any,
    claim_specs_summary: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Judge relevance of a single claim to a single SQ.

    Args:
        claim_text: free-text finding from the solver
        sq_text: text_gloss of the sub-question
        sq_focus_variables: variables the SQ investigates
        sq_tier: "high", "medium", or "low"
        sq_answer_keys: list of render_answer_key() outputs for the SQ's specs
        brief_text: research brief (1-3 sentence summary preferred)
        llm_call: callable(system: str, user: str) -> str
        claim_specs_summary: optional list of {comparison_kind, measurement_kind,
            primary_vars} derived from the claim's compiled specs

    Returns:
        {"relevance": float, "reasoning": str, "raw": str}
    """
    # -- Build SQ answer key section --
    sq_ak_lines = []
    for i, ak in enumerate(sq_answer_keys):
        role_tag = ""
        if "role" in ak:
            role_tag = f" [{ak['role']}]"
        sq_ak_lines.append(
            f"  Spec {i + 1}{role_tag}: {ak.get('result_type', '?')} "
            f"— {ak.get('headline', 'no headline')} "
            f"({ak.get('meta', {}).get('measurement_kind', '?')}/"
            f"{ak.get('meta', {}).get('comparison_kind', '?')})"
        )
    sq_answer_keys_section = ""
    if sq_ak_lines:
        sq_answer_keys_section = (
            "Answer key (SQ semantics — do NOT judge correctness):\n"
            + "\n".join(sq_ak_lines)
        )

    # -- Build claim specs section --
    claim_specs_section = ""
    if claim_specs_summary:
        lines = []
        for cs in claim_specs_summary:
            lines.append(
                f"  - {cs.get('measurement_kind', '?')} / "
                f"{cs.get('comparison_kind', '?')} "
                f"on {cs.get('primary_vars', '?')}"
            )
        claim_specs_section = "Claim structure:\n" + "\n".join(lines)

    user_prompt = _build_user_prompt(
        brief=brief_text or "(no brief provided)",
        sq_text=sq_text,
        sq_focus_vars=", ".join(sq_focus_variables) if sq_focus_variables else "(none)",
        sq_tier=sq_tier,
        sq_answer_keys_section=sq_answer_keys_section,
        claim_text=claim_text,
        claim_specs_section=claim_specs_section,
    )

    # -- Call LLM --
    raw = llm_call(SYSTEM_PROMPT, user_prompt)

    # -- Parse response --
    return _parse_judge_response(raw)


def _parse_judge_response(raw: str) -> dict[str, Any]:
    """Parse LLM response into structured result. Tolerant of formatting."""
    # Try JSON extraction
    try:
        # Find JSON in response (may be wrapped in markdown code block)
        json_match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            relevance = float(parsed.get("relevance", 0.0))
            relevance = max(0.0, min(1.0, relevance))
            reasoning = str(parsed.get("reasoning", ""))
            return {"relevance": relevance, "reasoning": reasoning, "raw": raw}
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: look for a bare number
    num_match = re.search(r"\b(0(?:\.\d+)?|1(?:\.0+)?)\b", raw)
    if num_match:
        relevance = float(num_match.group())
        logger.warning("judge_relevance: parsed bare number %.2f from: %s", relevance, raw[:100])
        return {"relevance": relevance, "reasoning": "(parsed from unstructured)", "raw": raw}

    # Total failure
    logger.warning("judge_relevance: could not parse response: %s", raw[:200])
    return {"relevance": 0.0, "reasoning": "(parse failure)", "raw": raw}


# ---------------------------------------------------------------------------
# Batch helper: score all claims against all SQs
# ---------------------------------------------------------------------------


def _extract_claim_vars(claim: dict[str, Any]) -> set[str]:
    """Extract variable names from claim specs summary for pre-filtering."""
    specs = claim.get("specs_summary", [])
    if not specs:
        return set()
    result: set[str] = set()
    for cs in specs:
        pv = cs.get("primary_vars", "")
        if isinstance(pv, str) and pv:
            result.update(v.strip() for v in pv.split(",") if v.strip())
        elif isinstance(pv, (list, tuple)):
            result.update(str(v) for v in pv)
    return result


def judge_all_claims(
    claims: list[dict[str, Any]],
    sqs: list[dict[str, Any]],
    brief_text: str,
    llm_call: Any,
) -> list[dict[str, Any]]:
    """Score every claim against every SQ. Returns list of scored pairs.

    Args:
        claims: list of {"claim_id", "claim_text", "specs_summary"?}
        sqs: list of {"sq_id", "text_gloss", "focus_variables", "tier",
             "answer_keys": [render_answer_key outputs]}
        brief_text: research brief
        llm_call: callable(system, user) -> str

    Returns:
        list of {"claim_id", "sq_id", "relevance", "reasoning"}
    """
    results = []
    for claim in claims:
        best_relevance = 0.0
        best_sq_id = None
        best_reasoning = ""

        claim_vars = _extract_claim_vars(claim)

        for sq in sqs:
            sq_vars = set(sq.get("focus_variables", ()))

            # Pre-filter: if both have variables and no overlap, skip LLM call
            if claim_vars and sq_vars and not claim_vars & sq_vars:
                results.append({
                    "claim_id": claim["claim_id"],
                    "sq_id": sq["sq_id"],
                    "relevance": 0.0,
                    "reasoning": "(no variable overlap — skipped)",
                })
                continue

            r = judge_relevance(
                claim_text=claim["claim_text"],
                sq_text=sq["text_gloss"],
                sq_focus_variables=tuple(sq.get("focus_variables", ())),
                sq_tier=sq.get("tier", "medium"),
                sq_answer_keys=sq.get("answer_keys", []),
                brief_text=brief_text,
                llm_call=llm_call,
                claim_specs_summary=claim.get("specs_summary"),
            )

            results.append({
                "claim_id": claim["claim_id"],
                "sq_id": sq["sq_id"],
                "relevance": r["relevance"],
                "reasoning": r["reasoning"],
            })

            if r["relevance"] > best_relevance:
                best_relevance = r["relevance"]
                best_sq_id = sq["sq_id"]
                best_reasoning = r["reasoning"]

        logger.info(
            "  claim %s: best match sq=%s (rel=%.2f): %s",
            claim["claim_id"],
            best_sq_id,
            best_relevance,
            best_reasoning[:80],
        )

    return results
