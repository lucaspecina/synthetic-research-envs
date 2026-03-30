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
from dataclasses import dataclass, field
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
# Extraction context — rich context from the pipeline
# ---------------------------------------------------------------------------


@dataclass
class ExtractionContext:
    """Investigation context passed to the extraction LLM.

    Provides the brief, domain info, variable descriptions, and sub-questions
    so the LLM can disambiguate claims in context. Without this, the LLM only
    sees variable names and must guess what the investigation was about.

    S03 A/B test (2026-03-30): adding context eliminates invalid variable names
    in conditioning_set and recovers claims from unnecessary abstention, without
    introducing observable bias toward sub-question patterns.
    """

    research_brief: str = ""
    domain: str = ""
    description: str = ""
    title: str = ""
    sub_questions: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a scientific claim compiler. Your job is to extract the structured
intent from a natural-language research claim.

Given a claim and the variables available in the world, extract one or more
verifiable assertions. If the claim fits a single pattern, output ONE intent
object. If it contains MULTIPLE distinct assertions (chain: X->M->Y->Z, or
fork: X->Y AND X->Z), output a wrapper with multiple intents.

## Output format — single assertion (most common)
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

## Output format — multiple assertions (compound claims)
{
  "intents": [
    { <intent object as above> },
    { <intent object as above> }
  ]
}

## Output format — abstention
{
  "abstention": true,
  "reason": "<brief explanation>"
}

## CRITICAL: when to use multiple intents vs a single rich pattern
- "A affects Y through M" = ONE mediation intent (NOT two pairwise intents)
- "A confounds the X->Y relationship" = ONE confounding intent
- "The effect of X on Y depends on Z" = ONE heterogeneity intent
- "X is the strongest predictor of Y among A, B, C" = ONE effect_ranking intent
- "A is associated with Y controlling for B, C" = ONE observational_association
ONLY use multiple intents when the claim makes SEPARATE assertions that
cannot fit in a single pattern. Example: "A increases B, B increases C,
and C decreases D" = 3 separate observational_association intents.

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
- "near_zero" direction means the estimated coefficient is close to zero in magnitude.
- CRITICAL: direction reflects the SIGN of the estimated slope/coefficient, NOT its
  statistical significance. A slope of -3.83 is "negative" even if p > 0.05.
  Use "near_zero" ONLY when the coefficient itself is close to zero, not when
  the p-value is large.
- CRITICAL: extract the solver's CONCLUSION, not per-dataset raw findings. If the
  claim reports "r = -0.19 in dataset A, r = +0.25 in dataset B", extract the
  overall conclusion the solver draws, not separate contradictory intents.
- ALL variable names in treatment, outcome, mediator, modifier, confounder,
  conditioning_set, and ranking_vars MUST appear in the provided Variables list.
  Dataset names (dataset_bg, dataset_survey), row identifiers (site_id, wave),
  and other non-variable columns must NEVER appear in these fields.
- Output ONLY valid JSON, no explanations."""


def _build_context_block(ctx: ExtractionContext) -> str:
    """Build the investigation context block for the system prompt."""
    parts: list[str] = []
    parts.append(
        "\n\n## Investigation context (for disambiguation, NOT to force matching)\n"
        "This context helps you understand what the investigation was about.\n"
        "Extract what the claim ACTUALLY says, not what would best match a question."
    )
    if ctx.research_brief:
        parts.append(f"\n### Research brief\n{ctx.research_brief}")
    if ctx.description:
        parts.append(f"\n### Domain context\n{ctx.description[:600]}")
    if ctx.sub_questions:
        sq_lines = []
        for sq in ctx.sub_questions:
            gloss = sq.get("text_gloss") or sq.get("sq_id", "?")
            pattern = sq.get("pattern", "?")
            sq_lines.append(f"- {sq.get('sq_id', '?')}: {gloss} (pattern={pattern})")
        parts.append(
            "\n### Investigation sub-questions (hidden from solver, for context only)\n"
            + "\n".join(sq_lines)
        )
    return "\n".join(parts)


def build_extraction_prompt(
    claim: ClaimCard,
    world_variables: list[str],
    n_exemplars: int = 5,
    context: ExtractionContext | None = None,
) -> list[dict[str, str]]:
    """Build the messages list for LLM extraction.

    Returns a list of message dicts suitable for a chat API:
    [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}, ...]

    Args:
        claim: The ClaimCard to compile.
        world_variables: List of variable names in the world.
        n_exemplars: Number of positive exemplars to include.
        context: Optional investigation context (brief, domain, SQs).
    """
    system = _SYSTEM_PROMPT
    if context:
        system += _build_context_block(context)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system},
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


def _parse_single_intent(data: dict[str, Any], claim_id: str, idx: int = 0) -> ClaimIntent:
    """Parse a single intent dict into a ClaimIntent. Raises on invalid fields."""
    return ClaimIntent(
        claim_id=f"{claim_id}::{idx}",
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


def parse_extraction_response(
    response_text: str,
    claim_id: str,
) -> list[ClaimIntent] | CompilerOutput:
    """Parse LLM response into list of ClaimIntents or CompilerOutput (abstention).

    Accepts 3 formats:
    - Legacy single: {"pattern": ..., "treatment": ..., "outcome": ...}
    - Multi-unit wrapper: {"intents": [{...}, {...}]}
    - Abstention: {"abstention": true, "reason": "..."}

    Returns:
        list[ClaimIntent] if successfully parsed (1 or more intents).
        CompilerOutput with abstention if the LLM abstained or parsing failed.
    """
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

    # Abstention
    if isinstance(data, dict) and data.get("abstention"):
        return CompilerOutput(
            claim_id=claim_id,
            status="abstention",
            abstention_reason=data.get("reason", "LLM abstained"),
        )

    # Multi-unit wrapper: {"intents": [...]}
    if isinstance(data, dict) and "intents" in data:
        intent_list = data["intents"]
        if not isinstance(intent_list, list) or len(intent_list) == 0:
            return CompilerOutput(
                claim_id=claim_id,
                status="abstention",
                abstention_reason="Empty intents array in wrapper",
            )
        parsed: list[ClaimIntent] = []
        for idx, item in enumerate(intent_list):
            try:
                parsed.append(_parse_single_intent(item, claim_id, idx))
            except (KeyError, ValueError) as e:
                logger.warning("Intent %d failed for %s: %s", idx, claim_id, e)
        if not parsed:
            return CompilerOutput(
                claim_id=claim_id,
                status="abstention",
                abstention_reason="All intents in wrapper failed to parse",
            )
        return parsed

    # Legacy single intent: {"pattern": ..., ...}
    if isinstance(data, dict) and "pattern" in data:
        try:
            return [_parse_single_intent(data, claim_id)]
        except (KeyError, ValueError) as e:
            return CompilerOutput(
                claim_id=claim_id,
                status="abstention",
                abstention_reason=f"Invalid intent fields: {e}",
            )

    return CompilerOutput(
        claim_id=claim_id,
        status="abstention",
        abstention_reason=f"Unrecognized response format: {str(data)[:200]}",
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
    context: ExtractionContext | None = None,
) -> CompilerOutput:
    """Compile one ClaimCard through the full pipeline.

    Pipeline: prompt → LLM → parse → validate → lower → output.

    Handles multi-unit claims (A22): compound claims produce N intents,
    each lowered independently to a CompiledUnit. Final CompilerOutput
    collects all units with status compiled/partial/abstention.

    Args:
        claim: The ClaimCard to compile.
        summary: WorldSummary for validation and lowering.
        llm_call: Callable that takes messages list and returns response string.
            If None, uses deterministic fallback.
        context: Optional investigation context (brief, domain, SQs).
    """
    from sreg.tools.oi_compiler import CompiledUnit, lower_intent

    world_vars = summary.observable_names

    if llm_call is not None:
        # LLM extraction path — fail closed on errors
        try:
            messages = build_extraction_prompt(claim, world_vars, context=context)
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
        # Deterministic fallback returns single ClaimIntent | CompilerOutput
        det = _deterministic_extract(claim, world_vars)
        parsed = det if isinstance(det, CompilerOutput) else [det]

    # If parsing produced an abstention, return it
    if isinstance(parsed, CompilerOutput):
        logger.info(
            "Compile %s -> ABSTENTION: %s",
            claim.claim_id, parsed.abstention_reason,
        )
        return parsed

    # Lower each intent to a CompiledUnit
    intents: list[ClaimIntent] = parsed
    all_units: list[CompiledUnit] = []
    failures: list[str] = []

    for intent in intents:
        logger.info(
            "Compile %s -> pattern=%s treat=%s out=%s dir=%s",
            claim.claim_id, intent.pattern, intent.treatment, intent.outcome,
            intent.direction,
        )
        try:
            result = lower_intent(intent, summary)
            if result.compiled:
                all_units.extend(result.units)
            else:
                failures.append(result.abstention_reason or "Unknown lowering failure")
        except Exception as e:
            failures.append(f"Lowering failed for {intent.claim_id}: {e}")

    # Assemble final output
    if not all_units:
        return CompilerOutput(
            claim_id=claim.claim_id,
            status="abstention",
            abstention_reason=(
                f"All {len(intents)} intent(s) failed to lower: "
                + "; ".join(failures)
            ),
        )

    status = "compiled" if not failures else "partial"
    return CompilerOutput(
        claim_id=claim.claim_id,
        status=status,
        units=all_units,
        uncompiled_fragments=failures,
    )


def compile_episode_claims(
    claims: list[ClaimCard],
    summary: WorldSummary,
    llm_call: Any | None = None,
    context: ExtractionContext | None = None,
) -> list[CompilerOutput]:
    """Compile all claims for an episode."""
    return [compile_claim(c, summary, llm_call, context) for c in claims]


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
    "ExtractionContext",
    "build_extraction_prompt",
    "compile_claim",
    "compile_episode_claims",
    "parse_extraction_response",
]
