"""OI Compiler LLM Extraction: ClaimCard -> ClaimIntent via few-shot prompting.

This module handles the LLM step in the compiler pipeline:
    ClaimCard -> [build_prompt + exemplars] -> [LLM] -> [parse + validate] -> ClaimIntent

Separation of concerns:
- Prompt construction: deterministic, no LLM needed
- Response parsing: deterministic, no LLM needed
- LLM call: pluggable, can be mocked for testing
- Validation: uses validate_intent() from oi_compiler

The module can work without an LLM by using the deterministic fallback
(keyword-based pattern matching) for testing and development.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sreg.models.open_investigation import ClaimCard
from sreg.tools.oi_compiler import (
    ClaimIntent,
    CompilerOutput,
    Direction,
    PatternClass,
    WorldSummary,
)
from sreg.tools.oi_exemplars import get_abstention_exemplars, get_positive_exemplars

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a scientific claim compiler. Your job is to extract the structured
intent from a natural-language research claim.

Given a claim and the variables available in the world, output a JSON object
with the fields below. If the claim cannot be compiled (too vague, about
model fit, about sample properties), output {"abstention": true, "reason": "..."}.

## Output format (compiled)
{
  "pattern": "<causal_effect|mediation|heterogeneity|tail_risk|variance_effect|\
observational_association|effect_ranking|confounding>",
  "treatment": "<main cause variable name>",
  "outcome": "<main outcome variable name>",
  "direction": "<positive|negative|near_zero>",
  "mediator": "<variable name or null>",
  "modifier": "<variable name or null>",
  "confounder": "<variable name or null>",
  "ranking_vars": ["<var1>", "<var2>", ...],
  "conditioning_set": ["<var1>", ...],
  "evidence_type": "<interventional|observational>"
}

## Output format (abstention)
{
  "abstention": true,
  "reason": "<brief explanation>"
}

## Rules
- Variable names must EXACTLY match the world's variable list.
- Use "interventional" evidence_type for causal claims, "observational" for associations.
- For mediation: treatment is the initial cause, outcome is the final effect,
  mediator is the intermediate variable.
- For heterogeneity: treatment and outcome as usual, modifier is the variable
  that modulates the effect.
- For confounding: treatment and outcome as usual, confounder is the variable
  that creates a spurious or inflated association between them.
- For effect_ranking: list ALL variables being compared in ranking_vars.
- If the claim uses causal language but the evidence is purely observational,
  still set pattern to the causal type but mark evidence_type as "observational".
- "near_zero" direction means no meaningful effect was found. This is a valid finding.
- Output ONLY valid JSON, no explanations."""


def build_extraction_prompt(
    claim: ClaimCard,
    world_variables: list[str],
    n_exemplars: int = 5,
) -> list[dict[str, str]]:
    """Build the messages list for LLM extraction.

    Returns a list of message dicts suitable for a chat API:
    [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}, ...]

    Args:
        claim: The ClaimCard to compile.
        world_variables: List of variable names in the world.
        n_exemplars: Number of positive exemplars to include.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
    ]

    # Few-shot examples (positive)
    positives = get_positive_exemplars()[:n_exemplars]
    for text, intent in positives:
        messages.append({
            "role": "user",
            "content": f"Claim: \"{text}\"\nVariables: {intent.treatment}, {intent.outcome}"
            + (f", {intent.mediator}" if intent.mediator else "")
            + (f", {intent.modifier}" if intent.modifier else ""),
        })
        intent_dict = _intent_to_json(intent)
        messages.append({
            "role": "assistant",
            "content": json.dumps(intent_dict),
        })

    # Few-shot examples (abstention — first 2)
    abstentions = get_abstention_exemplars()[:2]
    for text, reason in abstentions:
        messages.append({
            "role": "user",
            "content": f"Claim: \"{text}\"\nVariables: A, Y, C, Z",
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps({"abstention": True, "reason": reason}),
        })

    # Actual claim to compile
    var_list = ", ".join(world_variables)
    user_content = f"Claim: \"{claim.claim_text}\"\nVariables: {var_list}"
    if claim.focus_variables:
        user_content += f"\nFocus variables: {', '.join(claim.focus_variables)}"
    if claim.pattern_tags:
        user_content += f"\nPattern hints: {', '.join(claim.pattern_tags)}"

    messages.append({"role": "user", "content": user_content})

    return messages


def _intent_to_json(intent: ClaimIntent) -> dict[str, Any]:
    """Convert a ClaimIntent to the JSON format the LLM should produce."""
    result: dict[str, Any] = {
        "pattern": intent.pattern.value,
        "treatment": intent.treatment,
        "outcome": intent.outcome,
        "direction": intent.direction.value,
        "evidence_type": intent.evidence_type,
    }
    if intent.mediator:
        result["mediator"] = intent.mediator
    if intent.modifier:
        result["modifier"] = intent.modifier
    if intent.confounder:
        result["confounder"] = intent.confounder
    if intent.ranking_vars:
        result["ranking_vars"] = intent.ranking_vars
    if intent.conditioning_set:
        result["conditioning_set"] = intent.conditioning_set
    return result


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_extraction_response(
    response_text: str,
    claim_id: str,
) -> CompilerOutput | ClaimIntent:
    """Parse LLM response into ClaimIntent or CompilerOutput (abstention).

    Returns:
        ClaimIntent if successfully parsed.
        CompilerOutput with abstention if the LLM abstained or parsing failed.
    """
    # Extract JSON from response (may have markdown fencing)
    json_str = _extract_json(response_text)
    if json_str is None:
        return CompilerOutput(
            claim_id=claim_id,
            status="abstention",
            abstention_reason=f"Could not parse JSON from response: {response_text[:200]}",
        )

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        return CompilerOutput(
            claim_id=claim_id,
            status="abstention",
            abstention_reason=f"Invalid JSON: {e}",
        )

    # Check for abstention
    if data.get("abstention"):
        return CompilerOutput(
            claim_id=claim_id,
            status="abstention",
            abstention_reason=data.get("reason", "LLM abstained"),
        )

    # Parse as ClaimIntent
    try:
        intent = ClaimIntent(
            claim_id=claim_id,
            pattern=PatternClass(data["pattern"]),
            treatment=data["treatment"],
            outcome=data["outcome"],
            direction=Direction(data.get("direction", "positive")),
            mediator=data.get("mediator"),
            modifier=data.get("modifier"),
            confounder=data.get("confounder"),
            ranking_vars=data.get("ranking_vars", []),
            conditioning_set=data.get("conditioning_set", []),
            evidence_type=data.get("evidence_type", "interventional"),
        )
        return intent
    except (KeyError, ValueError) as e:
        return CompilerOutput(
            claim_id=claim_id,
            status="abstention",
            abstention_reason=f"Invalid intent fields: {e}",
        )


def _extract_json(text: str) -> str | None:
    """Extract JSON from text that may have markdown fencing."""
    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try raw JSON (find first { ... })
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0).strip()

    return None


# ---------------------------------------------------------------------------
# Full extraction pipeline
# ---------------------------------------------------------------------------


def compile_claim(
    claim: ClaimCard,
    summary: WorldSummary,
    llm_call: Any | None = None,
) -> CompilerOutput:
    """Compile one ClaimCard through the full pipeline.

    Pipeline: prompt → LLM → parse → validate → lower → output.

    Args:
        claim: The ClaimCard to compile.
        summary: WorldSummary for validation and lowering.
        llm_call: Callable that takes messages list and returns response string.
            If None, uses deterministic fallback.
    """
    from sreg.tools.oi_compiler import lower_intent

    world_vars = summary.observable_names

    if llm_call is not None:
        # LLM extraction path — fail closed on errors
        try:
            messages = build_extraction_prompt(claim, world_vars)
            response_text = llm_call(messages)
            if not isinstance(response_text, str):
                response_text = str(response_text)
            parsed = parse_extraction_response(response_text, claim.claim_id)
        except Exception as e:
            logger.warning("LLM extraction failed for %s: %s", claim.claim_id, e)
            return CompilerOutput(
                claim_id=claim.claim_id,
                status="abstention",
                abstention_reason=f"LLM extraction error: {e}",
            )
    else:
        # Deterministic fallback
        parsed = _deterministic_extract(claim, world_vars)

    # If parsing produced an abstention, return it
    if isinstance(parsed, CompilerOutput):
        return parsed

    # Lower to AtomicSpecs (lower_intent validates + lowers → CompilerOutput)
    intent = parsed
    try:
        result = lower_intent(intent, summary)
    except Exception as e:
        return CompilerOutput(
            claim_id=claim.claim_id,
            status="abstention",
            abstention_reason=f"Lowering failed: {e}",
        )

    return result


def compile_episode_claims(
    claims: list[ClaimCard],
    summary: WorldSummary,
    llm_call: Any | None = None,
) -> list[CompilerOutput]:
    """Compile all claims for an episode."""
    return [compile_claim(c, summary, llm_call) for c in claims]


# ---------------------------------------------------------------------------
# Deterministic fallback (keyword-based, for testing without LLM)
# ---------------------------------------------------------------------------

# Pattern keywords: (pattern, required_keyword_sets)
_PATTERN_KEYWORDS: list[tuple[PatternClass, list[str]]] = [
    (PatternClass.MEDIATION, ["mediat", "indirect", "through", "via", "pathway"]),
    (PatternClass.HETEROGENEITY, ["depend", "modif", "moder", "varies by", "interact"]),
    (PatternClass.TAIL_RISK, ["extreme", "tail", "risk", "severe", "above.*percentile"]),
    (PatternClass.VARIANCE_EFFECT, ["varian", "variabil", "spread", "dispersion"]),
    (PatternClass.OBSERVATIONAL_ASSOCIATION, [
        "associat", "correlat", "controlling for", "adjusting for",
    ]),
    (PatternClass.EFFECT_RANKING, ["strongest", "ranking", "most important", "primary driver"]),
    (PatternClass.CAUSAL_EFFECT, [
        "caus", "effect", "increas", "decreas", "raises", "lowers", "leads to",
    ]),
]

_NEGATIVE_KEYWORDS = ["no significant", "near zero", "no meaningful", "negligible", "no effect"]
_POSITIVE_KEYWORDS = ["positive", "increase", "raise", "higher", "improve", "benefit"]
_NEGATIVE_DIRECTION_KEYWORDS = [
    "negative", "decrease", "lower", "reduce", "worsen", "decline",
]


def _deterministic_extract(
    claim: ClaimCard,
    world_vars: list[str],
) -> ClaimIntent | CompilerOutput:
    """Keyword-based extraction fallback for testing.

    Uses claim_text + focus_variables + pattern_tags to guess the intent.
    NOT production quality — only for testing the pipeline without LLM.
    """
    text = claim.claim_text.lower()
    focus = claim.focus_variables or []

    # Detect pattern
    pattern = PatternClass.CAUSAL_EFFECT  # default
    if claim.pattern_tags:
        for tag in claim.pattern_tags:
            try:
                pattern = PatternClass(tag)
                break
            except ValueError:
                continue
    else:
        for pat, keywords in _PATTERN_KEYWORDS:
            if any(re.search(kw, text) for kw in keywords):
                pattern = pat
                break

    # Detect direction
    direction = Direction.POSITIVE
    if any(kw in text for kw in _NEGATIVE_KEYWORDS):
        direction = Direction.NEAR_ZERO
    elif any(kw in text for kw in _NEGATIVE_DIRECTION_KEYWORDS):
        direction = Direction.NEGATIVE

    # Extract variable roles ONLY from focus_variables (strict: no text scanning)
    valid_focus = [v for v in focus if v in world_vars]
    if len(valid_focus) < 2:
        return CompilerOutput(
            claim_id=claim.claim_id,
            status="abstention",
            abstention_reason="Could not identify treatment and outcome variables",
        )

    treatment = valid_focus[0]
    outcome = valid_focus[1]

    # Pattern-specific role extraction
    mediator = (
        valid_focus[2] if pattern == PatternClass.MEDIATION and len(valid_focus) > 2
        else None
    )
    modifier = (
        valid_focus[2] if pattern == PatternClass.HETEROGENEITY and len(valid_focus) > 2
        else None
    )

    kwargs: dict[str, Any] = {
        "claim_id": claim.claim_id,
        "pattern": pattern,
        "treatment": treatment,
        "outcome": outcome,
        "direction": direction,
    }
    if mediator:
        kwargs["mediator"] = mediator
    if modifier:
        kwargs["modifier"] = modifier
    if pattern == PatternClass.EFFECT_RANKING and len(valid_focus) >= 2:
        kwargs["ranking_vars"] = valid_focus[:3]
    if pattern == PatternClass.OBSERVATIONAL_ASSOCIATION:
        kwargs["conditioning_set"] = valid_focus[2:5]
        kwargs["evidence_type"] = "observational"

    try:
        return ClaimIntent(**kwargs)
    except (ValueError, KeyError) as e:
        return CompilerOutput(
            claim_id=claim.claim_id,
            status="abstention",
            abstention_reason=f"Deterministic extraction failed: {e}",
        )


__all__ = [
    "build_extraction_prompt",
    "compile_claim",
    "compile_episode_claims",
    "parse_extraction_response",
]
