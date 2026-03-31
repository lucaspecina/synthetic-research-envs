"""SQ v2 compile step: text_gloss -> VerificationSpec bundle.

Implements Camino B from sq_v2_matching_spec.md:
- Orchestrator generates SQ as text (sq_id, text_gloss, focus_variables, tier)
- This module compiles to SubQuestionIntentV2 with verification_specs

The LLM produces AtomicSpec(s) directly using the composable grammar.
No PatternClass, no routing, no catalog.

Invariants:
1. Every SQ produces at least 1 valid spec
2. Specs use only variables from the world
3. Specs are executable by the verifier
4. At least 1 spec is "required"
5. Uses LLM + grammar (same approach as S04 direct-to-atoms)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from sreg.models.open_investigation import (
    AtomicSpec,
    SQTier,
    SubQuestionIntentV2,
    VerificationSpec,
)
from sreg.tools.oi_compiler import WorldSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Grammar reference (shared with S04 direct_to_atoms prototype)
# ---------------------------------------------------------------------------

GRAMMAR_REF = """
You have a composable verification grammar with 4 pieces:

## QueryArm
Each spec has 1+ arms. Each arm generates data from the SCM.
- kind: "baseline" (sample from joint), "intervene" (do-calculus, set values),
  "observe" (observe natural distribution), "condition" (condition on values),
  "adjust" (observe but adjust for confounders), "sweep" (vary a variable)
- label: unique name for this arm (e.g. "baseline", "treated", "control")
- values: dict of variable=value for intervene/condition (e.g. {"X": 1.0})
- condition_on: dict for condition kind
- treatment/outcome: for adjust kind
- adjust_set: tuple of variable names to adjust for (for adjust kind)

## Measurement
What to compute from the sampled data.
- kind: "mean", "variance", "correlation", "partial_correlation",
  "tail_prob", "prob", "quantile", "identifiability_check"
- target: variable name for mean/variance/quantile/tail_prob
- lhs, rhs: variable names for correlation/partial_correlation
- cond_set: tuple of variables to condition on (for partial_correlation)
- treatment, outcome: for identifiability_check
- threshold: for tail_prob
- q: quantile level (0-1) for quantile

## Comparison
How to relate measurements across arms.
- kind: "identity" (single arm, just check the value),
  "difference" (arm1 - arm2), "ratio", "ranking" (rank multiple arms),
  "gap" (check minimum gap), "contrast_diff"
- ref_arm: reference arm label for difference/ratio
- order: tuple of arm labels for ranking
- tolerance: float (default 0.05)

## Assertion
What should be true about the comparison result.
- kind: "positive", "negative", "near_zero", "greater_than", "less_than",
  "rank_order", "identifiable", "not_identifiable",
  "changepoint_exists", "sign_flip", "gap_material",
  "distinguishable", "not_distinguishable"
- threshold: numeric threshold (default 0.0)
- tolerance: float (default 0.05)
- order: tuple of arm labels for rank_order

## AtomicSpec structure
{
  "spec_id": "unique_id",
  "arms": [{"label": "...", "kind": "...", ...}],
  "measurement": {"kind": "...", ...},
  "comparison": {"kind": "...", ...},
  "assertion": {"kind": "...", ...}
}

IMPORTANT RULES:
- ALL variable names must come from the provided Variables list.
- Each spec checks ONE atomic fact.
- For partial_correlation with empty cond_set, it computes raw correlation.
- "baseline" arms sample from the joint distribution (no intervention).
- Return a JSON array of spec objects.
"""

# ---------------------------------------------------------------------------
# Compile prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = f"""You are a verification compiler for a research evaluation system.

Given a sub-question (an investigation need) and world variables, produce
AtomicSpec(s) that would verify whether a solver has addressed this need.

{GRAMMAR_REF}

## Role assignment
For each spec, assign a role:
- "required": the spec that directly answers the core of the sub-question.
  A solver MUST cover this to get credit. At least 1 spec must be required.
- "support": additional evidence that strengthens the answer but isn't
  strictly necessary. A solver covering only support specs gets partial credit.

## Output format
Return a JSON array where each element has:
{{
  "spec": {{ ... AtomicSpec ... }},
  "role": "required" | "support"
}}

Think step by step:
1. What evidence would answer this sub-question?
2. What is the CORE measurement needed? (-> required)
3. What ADDITIONAL measurements would strengthen the answer? (-> support)
4. Compose each into an AtomicSpec using the grammar.

Return ONLY the JSON array. No explanation."""


def _build_variables_info(summary: WorldSummary) -> str:
    """Format world variables for the LLM prompt."""
    lines = []
    for name in summary.observable_names:
        va = summary.variables.get(name)
        if va:
            lines.append(
                f"- {name}: mean={va.mean:.3f}, std={va.std:.3f}, "
                f"range=[{va.p10:.3f}, {va.p90:.3f}]"
            )
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def _build_user_prompt(
    text_gloss: str,
    focus_variables: tuple[str, ...],
    variables_info: str,
    world_summary_text: str | None = None,
) -> str:
    """Build the user message for the compile step."""
    parts = [
        f'Sub-question: "{text_gloss}"',
        f"\nVariables in this world:\n{variables_info}",
    ]
    if focus_variables:
        parts.append(f"\nFocus variables: {', '.join(focus_variables)}")
    if world_summary_text:
        parts.append(f"\nWorld context: {world_summary_text}")
    parts.append("\nProduce AtomicSpec(s) with roles to verify this sub-question.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


def _parse_specs_json(raw: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    text = raw.strip()

    # Remove markdown code fences
    if "```" in text:
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("["):
                text = p
                break

    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    return []


def _coerce_tuples(d: dict) -> dict:
    """Convert lists to tuples where the model expects tuples."""
    for arm in d.get("arms", []):
        if "adjust_set" in arm and isinstance(arm["adjust_set"], list):
            arm["adjust_set"] = tuple(arm["adjust_set"])
        if "sweep_values" in arm and isinstance(arm["sweep_values"], list):
            arm["sweep_values"] = tuple(arm["sweep_values"])
        if "observed_vars" in arm and isinstance(arm["observed_vars"], list):
            arm["observed_vars"] = frozenset(arm["observed_vars"])
    meas = d.get("measurement", {})
    if "cond_set" in meas and isinstance(meas["cond_set"], list):
        meas["cond_set"] = tuple(meas["cond_set"])
    if "candidate_causes" in meas and isinstance(meas["candidate_causes"], list):
        meas["candidate_causes"] = tuple(meas["candidate_causes"])
    if "candidate_adjust_set" in meas and isinstance(meas["candidate_adjust_set"], list):
        meas["candidate_adjust_set"] = tuple(meas["candidate_adjust_set"])
    comp = d.get("comparison", {})
    if "order" in comp and isinstance(comp["order"], list):
        comp["order"] = tuple(comp["order"])
    assertion = d.get("assertion", {})
    if "order" in assertion and isinstance(assertion["order"], list):
        assertion["order"] = tuple(assertion["order"])
    arms = d.get("arms", [])
    if isinstance(arms, list):
        d["arms"] = tuple(arms)
    return d


def _validate_variables(spec_dict: dict, world_vars: set[str]) -> list[str]:
    """Check that all variable references in a spec exist in the world."""
    errors = []
    meas = spec_dict.get("measurement", {})
    for field in ("target", "lhs", "rhs", "treatment", "outcome"):
        val = meas.get(field)
        if val and isinstance(val, str) and val not in world_vars:
            errors.append(f"measurement.{field}={val} not in world variables")
        elif val and isinstance(val, (list, tuple)):
            for v in val:
                if v not in world_vars:
                    errors.append(f"measurement.{field} contains {v} not in world variables")
    for field in ("cond_set", "candidate_causes", "candidate_adjust_set"):
        vals = meas.get(field, ())
        for v in vals:
            if v not in world_vars:
                errors.append(f"measurement.{field} contains {v} not in world variables")
    for arm in spec_dict.get("arms", []):
        for v in arm.get("values", {}):
            if v not in world_vars:
                errors.append(f"arm.values contains {v} not in world variables")
        for v in arm.get("condition_on", {}):
            if v not in world_vars:
                errors.append(f"arm.condition_on contains {v} not in world variables")
        for v in arm.get("adjust_set", ()):
            if v not in world_vars:
                errors.append(f"arm.adjust_set contains {v} not in world variables")
        if arm.get("treatment") and arm["treatment"] not in world_vars:
            errors.append(f"arm.treatment={arm['treatment']} not in world variables")
        if arm.get("outcome") and arm["outcome"] not in world_vars:
            errors.append(f"arm.outcome={arm['outcome']} not in world variables")
    return errors


# ---------------------------------------------------------------------------
# Main compile function
# ---------------------------------------------------------------------------


class SQCompileResult:
    """Result of compiling a raw SQ to SubQuestionIntentV2."""

    def __init__(
        self,
        sq: SubQuestionIntentV2 | None = None,
        errors: list[str] | None = None,
        raw_response: str = "",
    ):
        self.sq = sq
        self.errors = errors or []
        self.raw_response = raw_response

    @property
    def success(self) -> bool:
        return self.sq is not None

    def __repr__(self) -> str:
        if self.success:
            n = len(self.sq.verification_specs)
            req = len(self.sq.required_specs)
            return f"SQCompileResult(ok, {n} specs, {req} required)"
        return f"SQCompileResult(FAIL, errors={self.errors})"


def compile_sq_to_specs(
    sq_id: str,
    text_gloss: str,
    focus_variables: tuple[str, ...],
    tier: SQTier,
    summary: WorldSummary,
    llm_call: Any,
    world_summary_text: str | None = None,
) -> SQCompileResult:
    """Compile a raw SQ (text) into SubQuestionIntentV2 with verification specs.

    This is the Camino B compile step: orchestrator generates SQ as text,
    this function converts to AtomicSpec bundle via LLM.

    Args:
        sq_id: unique identifier
        text_gloss: free-form SQ text from orchestrator
        focus_variables: variables involved (for pre-filter, not scoring)
        tier: importance tier (high/medium/low)
        summary: WorldSummary with variable anchors
        llm_call: callable(system: str, user: str) -> str
        world_summary_text: optional context about the world

    Returns:
        SQCompileResult with SubQuestionIntentV2 or errors
    """
    world_vars = set(summary.observable_names)
    variables_info = _build_variables_info(summary)

    user_prompt = _build_user_prompt(
        text_gloss, focus_variables, variables_info, world_summary_text
    )

    # Call LLM
    try:
        raw = llm_call(_SYSTEM_PROMPT, user_prompt)
        if not isinstance(raw, str):
            raw = str(raw)
    except Exception as e:
        logger.error("LLM call failed for SQ %s: %s", sq_id, e)
        return SQCompileResult(errors=[f"LLM call failed: {e}"])

    # Parse response
    try:
        items = _parse_specs_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("JSON parse failed for SQ %s: %s", sq_id, e)
        return SQCompileResult(errors=[f"JSON parse failed: {e}"], raw_response=raw)

    if not items:
        return SQCompileResult(
            errors=["LLM returned no specs"],
            raw_response=raw,
        )

    # Build VerificationSpecs
    vspecs: list[VerificationSpec] = []
    errors: list[str] = []

    for i, item in enumerate(items):
        # Handle both formats: {spec: ..., role: ...} or just the spec itself
        if "spec" in item and "role" in item:
            spec_dict = item["spec"]
            role = item["role"]
        elif "arms" in item:
            # Direct AtomicSpec format (no role wrapper)
            spec_dict = item
            role = "required" if i == 0 else "support"
        else:
            errors.append(f"Item {i}: unrecognized format")
            continue

        if role not in ("required", "support"):
            role = "required"

        # Validate variables
        var_errors = _validate_variables(spec_dict, world_vars)
        if var_errors:
            errors.extend(f"Item {i}: {e}" for e in var_errors)
            continue

        # Ensure spec_id
        if "spec_id" not in spec_dict:
            spec_dict["spec_id"] = f"{sq_id}_spec_{i}"

        # Coerce types and build AtomicSpec
        try:
            spec_dict = _coerce_tuples(spec_dict)
            atom = AtomicSpec(**spec_dict)
            vspecs.append(VerificationSpec(spec=atom, role=role))
        except (ValidationError, TypeError, ValueError) as e:
            errors.append(f"Item {i}: AtomicSpec validation failed: {e}")
            continue

    if not vspecs:
        return SQCompileResult(
            errors=errors or ["All specs failed validation"],
            raw_response=raw,
        )

    # Ensure at least one required
    if not any(vs.role == "required" for vs in vspecs):
        vspecs[0] = VerificationSpec(spec=vspecs[0].spec, role="required")

    # Build SubQuestionIntentV2
    try:
        sq = SubQuestionIntentV2(
            sq_id=sq_id,
            text_gloss=text_gloss,
            verification_specs=vspecs,
            tier=tier,
            focus_variables=focus_variables,
        )
    except ValidationError as e:
        return SQCompileResult(
            errors=[f"SubQuestionIntentV2 validation failed: {e}"],
            raw_response=raw,
        )

    if errors:
        logger.info(
            "SQ %s compiled with %d specs (%d warnings): %s",
            sq_id, len(vspecs), len(errors), "; ".join(errors),
        )

    return SQCompileResult(sq=sq, errors=errors, raw_response=raw)
