"""OI Compiler: grammar-direct LLM extraction (ClaimCard -> AtomicSpecs).

The LLM receives the claim text and the composable AtomicSpec grammar,
and produces AtomicSpecs directly — no intermediate representation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sreg.models.open_investigation import ClaimCard
from sreg.tools.oi_compiler import (
    CompilerOutput,
    WorldSummary,
)

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
    variable_descriptions: dict[str, str] = field(default_factory=dict)
    sub_questions: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Grammar-direct compilation (A23)
# ---------------------------------------------------------------------------


def compile_claim_direct(
    claim: ClaimCard,
    summary: WorldSummary,
    llm_call: Any,
) -> CompilerOutput | None:
    """Compile a ClaimCard directly to AtomicSpecs using the composable grammar.

    LLM produces AtomicSpecs directly from claim text. Same grammar used by
    the SQ compiler. Returns CompilerOutput on success, None on failure.
    """
    from sreg.models.open_investigation import AtomicSpec
    from sreg.tools.oi_compiler import CompiledUnit
    from sreg.tools.oi_sq_compiler import (
        GRAMMAR_REF,
        _build_variables_info,
        _coerce_tuples,
        _parse_specs_json,
        _validate_variables,
    )

    system_prompt = f"""You are a verification compiler for a research evaluation system.

Given a research claim and world variables, produce AtomicSpec(s) that verify
whether the claim is true according to a structural causal model (SCM).

{GRAMMAR_REF}

## Guidelines for claim compilation
- Extract ALL testable assertions from the claim text.
- Each AtomicSpec tests ONE atomic fact.
- A claim like "X causes Y and also affects Z" should produce 2+ specs.
- Causal claims ("X causes Y", "X leads to Y") need interventional arms.
- Associational claims ("X correlates with Y") use baseline arms with
  correlation or partial_correlation measurement.
- Claims about confounding need partial_correlation or interventional specs
  that show the gap between crude and adjusted effects.
- Mediation claims need specs comparing total vs direct effects.
- Methodological claims ("don't condition on X because it's downstream")
  can test whether X is a descendant: intervene on treatment, measure X.
  If X changes, it's downstream. Use "positive" or "negative" assertion.
- "No effect" or "null association" claims should use near_zero assertion.
- Direction: "increases" -> positive, "decreases" -> negative.
- For difference/ratio comparisons: ref_arm is REQUIRED and must be the
  control/baseline arm. Formula: difference = other_arm - ref_arm.
  "X increases Y" -> ref_arm = control arm, assertion = positive.

## Output format
Return a JSON array of AtomicSpec objects:
[
  {{ ... AtomicSpec ... }},
  ...
]

Return ONLY the JSON array. No explanation."""

    world_vars = set(summary.observable_names)
    variables_info = _build_variables_info(summary)

    # Build user prompt from claim
    parts = [
        f'Claim: "{claim.claim_text}"',
        f"\nVariables in this world:\n{variables_info}",
    ]
    if claim.focus_variables:
        parts.append(f"\nFocus variables: {', '.join(claim.focus_variables)}")
    parts.append("\nProduce AtomicSpec(s) to verify this claim.")
    user_prompt = "\n".join(parts)

    # Call LLM — try (system, user) first, fall back to messages list
    try:
        try:
            raw = llm_call(system_prompt, user_prompt)
        except TypeError:
            raw = llm_call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ])
        if not isinstance(raw, str):
            raw = str(raw)
    except Exception as e:
        logger.warning("Grammar-direct LLM call failed for %s: %s", claim.claim_id, e)
        return None

    # Parse response
    try:
        items = _parse_specs_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(
            "Grammar-direct JSON parse failed for %s: %s", claim.claim_id, e,
        )
        return None

    if not items:
        logger.warning("Grammar-direct returned no specs for %s", claim.claim_id)
        return None

    # Build AtomicSpecs
    specs: list[AtomicSpec] = []
    errors: list[str] = []

    for i, item in enumerate(items):
        # Handle wrapped {spec: ..., role: ...} or direct spec dict
        spec_dict = item
        if isinstance(item, dict) and "spec" in item:
            spec_dict = item["spec"]

        # Validate variables
        var_errors = _validate_variables(spec_dict, world_vars)
        if var_errors:
            errors.extend(f"Spec {i}: {e}" for e in var_errors)
            continue

        # Ensure spec_id
        if "spec_id" not in spec_dict:
            spec_dict["spec_id"] = f"{claim.claim_id}_direct_{i}"

        # Coerce types and build AtomicSpec
        try:
            spec_dict = _coerce_tuples(spec_dict)
            atom = AtomicSpec(**spec_dict)
            specs.append(atom)
        except Exception as e:
            errors.append(f"Spec {i}: validation failed: {e}")
            continue

    if not specs:
        logger.warning(
            "Grammar-direct: all specs failed for %s: %s",
            claim.claim_id, "; ".join(errors),
        )
        return None

    # Single unit with all specs — no ClaimIntent IR
    unit = CompiledUnit(
        unit_id=f"{claim.claim_id}_direct",
        intent=None,
        specs=specs,
        backend="grammar_direct",
    )

    logger.info(
        "Grammar-direct compile %s -> %d specs (%d errors)",
        claim.claim_id, len(specs), len(errors),
    )

    return CompilerOutput(
        claim_id=claim.claim_id,
        status="compiled" if not errors else "partial",
        units=[unit],
        uncompiled_fragments=errors,
    )


# ---------------------------------------------------------------------------
# Full extraction pipeline
# ---------------------------------------------------------------------------


def compile_claim(
    claim: ClaimCard,
    summary: WorldSummary,
    llm_call: Any | None = None,
    context: ExtractionContext | None = None,
) -> CompilerOutput:
    """Compile one ClaimCard via grammar-direct LLM extraction.

    Args:
        claim: The ClaimCard to compile.
        summary: WorldSummary for validation.
        llm_call: Callable for LLM calls. Required for compilation.
        context: Optional investigation context (brief, domain, SQs).
    """
    if llm_call is None:
        return CompilerOutput(
            claim_id=claim.claim_id,
            status="abstention",
            abstention_reason="No LLM available for grammar-direct compilation",
        )

    result = compile_claim_direct(claim, summary, llm_call)
    if result is not None and result.compiled:
        logger.info(
            "Compile %s -> grammar-direct: %d specs",
            claim.claim_id, len(result.specs),
        )
        return result

    return CompilerOutput(
        claim_id=claim.claim_id,
        status="abstention",
        abstention_reason="Grammar-direct compilation failed",
    )


def compile_episode_claims(
    claims: list[ClaimCard],
    summary: WorldSummary,
    llm_call: Any | None = None,
    context: ExtractionContext | None = None,
) -> list[CompilerOutput]:
    """Compile all claims for an episode."""
    return [compile_claim(c, summary, llm_call, context) for c in claims]



__all__ = [
    "ExtractionContext",
    "compile_claim",
    "compile_claim_direct",
    "compile_episode_claims",
]
