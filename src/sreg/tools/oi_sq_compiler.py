"""SQ v2 compile step: text_gloss -> VerificationSpec bundle + answer key grounding.

Implements Camino B from sq_v2_matching_spec.md:
- Orchestrator generates SQ as text (sq_id, text_gloss, focus_variables, tier)
- This module compiles to SubQuestionIntentV2 with verification_specs
- After compilation, ground_sq_answer_key() runs specs against SCM to fill verdicts

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
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from sreg.models.open_investigation import (
    AtomicSpec,
    AtomVerdict,
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
- condition_on: dict mapping variable name to a condition predicate.
  Available predicates:
  * Point value (shorthand): just a number, e.g. {"X": 5.0}
    Matches rows where X is approximately 5.0 (within 15% of std).
  * range: {"kind": "range", "lo": <number>, "hi": <number>}
    Matches rows where lo <= variable <= hi.
    Example: near a cutoff: {"eligibility_gap": {"kind": "range", "lo": -1000, "hi": 1000}}
  * quantile_range: {"kind": "quantile_range", "q_lo": <0-1>, "q_hi": <0-1>}
    Matches rows in the given quantile range of the variable's distribution.
    Example: bottom quartile: {"income": {"kind": "quantile_range", "q_lo": 0.0, "q_hi": 0.25}}
  * in_set: {"kind": "in_set", "values": [<value>, ...]}
    Matches rows where variable equals any listed value.
    Example: categorical: {"region": {"kind": "in_set", "values": ["urban", "suburban"]}}
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
  "difference", "ratio", "ranking" (rank multiple arms),
  "gap" (check minimum gap), "contrast_diff"
- ref_arm: REQUIRED for difference/ratio. The reference (baseline/control) arm.
  Formula: difference = other_arm - ref_arm. ratio = other_arm / ref_arm.
  Example: to test "treatment increases Y", set ref_arm to the control arm.
  If other_arm > ref_arm, difference is positive.
- order: tuple of arm labels for ranking
- tolerance: float (default 0.05)
- RULE: difference and ratio require EXACTLY 2 arms and ref_arm must be set.

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
- Do NOT reference derived or constructed variables. Use predicates on existing
  world variables instead. E.g., instead of a variable "eligible", use
  {"eligibility_gap": {"kind": "range", "lo": -1000, "hi": 1000}}.
- Each spec checks ONE atomic fact.
- For partial_correlation with empty cond_set, it computes raw correlation.
- "baseline" arms sample from the joint distribution (no intervention).
- ONE condition predicate per variable in condition_on.
- Do NOT condition on a variable already set in values (same arm).
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


def _strip_json_fences(raw: str) -> str:
    """Strip markdown code fences and return the inner JSON-like text.

    Mirrors the fence-stripping logic of `_parse_specs_json` so that
    abstention detection looks at the same effective payload the parser
    sees.
    """
    text = raw.strip()
    if "```" in text:
        for p in text.split("```"):
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("[") or p.startswith("{"):
                return p
    return text


def _is_explicit_abstention(raw: str) -> bool:
    """Detect a deliberate empty JSON array as the LLM's abstention signal.

    Returns True only when the LLM returned an explicit `[]` (after
    stripping markdown fences). This is the contract surface area for
    abstention as defined in the abstention exemplars block of the
    system prompt: a model-dependent claim that the grammar cannot
    verify is signalled by returning an empty array.

    Distinguishes deliberate abstention from:
    - empty raw response (LLM call returned ""), which is an error
    - non-array text (the LLM ignored the format), which is an error
    - parse failures inside a non-empty array, which are also errors
    """
    if not raw or not raw.strip():
        return False
    inner = _strip_json_fences(raw)
    if not (inner.startswith("[") and inner.endswith("]")):
        return False
    middle = inner[1:-1].strip()
    return middle == ""


def _parse_specs_json(raw: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    text = _strip_json_fences(raw)
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
    for fld in ("target", "lhs", "rhs", "treatment", "outcome"):
        val = meas.get(fld)
        if val and isinstance(val, str) and val not in world_vars:
            errors.append(f"measurement.{fld}={val} not in world variables")
        elif val and isinstance(val, (list, tuple)):
            for v in val:
                if v not in world_vars:
                    errors.append(f"measurement.{fld} contains {v} not in world variables")
    for fld in ("cond_set", "candidate_causes", "candidate_adjust_set"):
        vals = meas.get(fld, ())
        for v in vals:
            if v not in world_vars:
                errors.append(f"measurement.{fld} contains {v} not in world variables")
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
    """Result of compiling a raw SQ to SubQuestionIntentV2.

    Three terminal states are explicit:
    - success (sq is not None): the LLM produced at least one valid spec.
    - abstained (abstained=True): the LLM signalled deliberate abstention by
      returning an explicit empty array. The SQ is unanswerable by the
      grammar (model-dependent quantity, etc.) and intentionally left blank.
      Abstention is NOT a compile error — consumers should treat it as a
      legitimate "no specs by design" signal.
    - error (sq is None and not abstained): something went wrong (LLM call
      failed, JSON unparseable, all candidate specs failed validation).
      `errors` carries the details.

    Note: this contract is intentionally minimal. It distinguishes
    abstention from error and nothing else. Scoring, matching, and
    required-fallback policies are unchanged.
    """

    def __init__(
        self,
        sq: SubQuestionIntentV2 | None = None,
        errors: list[str] | None = None,
        raw_response: str = "",
        abstained: bool = False,
        abstain_reason: str | None = None,
    ):
        self.sq = sq
        self.errors = errors or []
        self.raw_response = raw_response
        self.abstained = abstained
        self.abstain_reason = abstain_reason

    @property
    def success(self) -> bool:
        return self.sq is not None

    def __repr__(self) -> str:
        if self.success:
            n = len(self.sq.verification_specs)
            req = len(self.sq.required_specs)
            return f"SQCompileResult(ok, {n} specs, {req} required)"
        if self.abstained:
            return f"SQCompileResult(ABSTAINED, reason={self.abstain_reason!r})"
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
        # Distinguish deliberate abstention (`[]`) from genuine compile error.
        # The abstention exemplars in the system prompt invite the LLM to
        # return an empty array when the SQ asks for a model-dependent
        # quantity. That is NOT a compile error.
        if _is_explicit_abstention(raw):
            logger.info(
                "SQ %s: compiler abstained (explicit empty-array signal)",
                sq_id,
            )
            return SQCompileResult(
                abstained=True,
                abstain_reason=(
                    "LLM returned an explicit empty array — deliberate "
                    "abstention per the abstention contract."
                ),
                raw_response=raw,
            )
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


# ---------------------------------------------------------------------------
# Semantic validation: does the compiled spec match the text_gloss intent?
# ---------------------------------------------------------------------------

# Keywords that imply causal / interventional intent
_CAUSAL_KEYWORDS = {
    "causally", "causal effect", "causal impact", "intervention",
    "do(", "if we intervene", "would happen if",
}

# Keywords that imply the text expects an increase
_INCREASE_KEYWORDS = {
    "increase", "increases", "worsen", "worsens", "raise", "raises",
    "higher", "more", "amplify", "amplifies", "exacerbate",
}

# Keywords that imply the text expects a decrease
_DECREASE_KEYWORDS = {
    "reduce", "reduces", "decrease", "decreases", "lower", "lowers",
    "mitigate", "mitigates", "diminish", "protect",
}

# Keywords for confounding questions
_CONFOUND_KEYWORDS = {
    "confound", "confounding", "confounded", "spurious", "explained by",
    "driven by", "mostly because", "apparent",
}

# Keywords for mediation questions
_MEDIATION_KEYWORDS = {
    "mediate", "mediated", "mediates", "through", "pathway", "indirect",
    "transmitted", "channel",
}

# Keywords for identifiability / unobserved
_IDENT_KEYWORDS = {
    "identifiable", "unobserved", "unmeasured", "latent", "hidden",
    "can we identify", "can the effect be identified",
}


def _text_has_keyword(text: str, keywords: set[str]) -> bool:
    """Check if text contains any of the keywords (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def validate_compilation_alignment(
    sq: SubQuestionIntentV2,
) -> list[dict[str, str]]:
    """Check if compiled specs align with the text_gloss intent.

    Returns a list of issues found. Each issue is a dict with:
    - severity: "warning" or "error"
    - check: name of the check
    - message: description of the problem

    Empty list = no issues found.
    """
    issues: list[dict[str, str]] = []
    text = sq.text_gloss
    specs = sq.verification_specs

    # --- Check 1: Causal text → interventional arms ---
    if _text_has_keyword(text, _CAUSAL_KEYWORDS):
        has_intervene = any(
            any(arm.kind == "intervene" for arm in vs.spec.arms)
            for vs in specs
            if vs.role == "required"
        )
        if not has_intervene:
            issues.append({
                "severity": "error",
                "check": "causal_needs_intervene",
                "message": (
                    "Text implies causal intent but no required spec uses "
                    "interventional arms. Observational specs alone cannot "
                    "verify causal claims."
                ),
            })

    # --- Check 2: Direction alignment ---
    required_specs = [vs for vs in specs if vs.role == "required"]
    if _text_has_keyword(text, _INCREASE_KEYWORDS):
        positive_assertions = {"positive", "greater_than"}
        has_positive = any(
            vs.spec.assertion and vs.spec.assertion.kind in positive_assertions
            for vs in required_specs
        )
        has_negative = any(
            vs.spec.assertion and vs.spec.assertion.kind == "negative"
            for vs in required_specs
        )
        if has_negative and not has_positive:
            issues.append({
                "severity": "warning",
                "check": "direction_mismatch",
                "message": (
                    "Text implies an increase but required spec asserts negative. "
                    "Check if the comparison direction is inverted."
                ),
            })

    if _text_has_keyword(text, _DECREASE_KEYWORDS):
        negative_assertions = {"negative", "less_than"}
        has_negative = any(
            vs.spec.assertion and vs.spec.assertion.kind in negative_assertions
            for vs in required_specs
        )
        has_positive = any(
            vs.spec.assertion and vs.spec.assertion.kind == "positive"
            for vs in required_specs
        )
        if has_positive and not has_negative:
            issues.append({
                "severity": "warning",
                "check": "direction_mismatch",
                "message": (
                    "Text implies a decrease but required spec asserts positive. "
                    "Check if the comparison direction is inverted."
                ),
            })

    # --- Check 3: Focus variables appear in specs ---
    if sq.focus_variables:
        spec_vars: set[str] = set()
        for vs in specs:
            m = vs.spec.measurement
            for field in ("target", "lhs", "rhs", "treatment", "outcome"):
                val = getattr(m, field, None)
                if isinstance(val, str):
                    spec_vars.add(val)
                elif isinstance(val, (tuple, list)):
                    spec_vars.update(str(v) for v in val)
            if m.cond_set:
                spec_vars.update(m.cond_set)
            for arm in vs.spec.arms:
                if arm.values:
                    spec_vars.update(arm.values.keys())

        missing = set(sq.focus_variables) - spec_vars
        if missing:
            issues.append({
                "severity": "warning",
                "check": "focus_vars_missing",
                "message": (
                    f"Focus variables {missing} not found in any spec. "
                    f"The compiled specs may not address the intended question."
                ),
            })

    # --- Check 4: Confounding text → appropriate specs ---
    if _text_has_keyword(text, _CONFOUND_KEYWORDS):
        has_confound_spec = any(
            vs.spec.measurement.kind in ("partial_correlation", "identifiability_check")
            for vs in required_specs
        )
        if not has_confound_spec:
            issues.append({
                "severity": "warning",
                "check": "confound_needs_conditioning",
                "message": (
                    "Text implies confounding analysis but no required spec "
                    "uses partial_correlation or identifiability_check."
                ),
            })

    # --- Check 5: Mediation text → appropriate specs ---
    if _text_has_keyword(text, _MEDIATION_KEYWORDS):
        has_multiple_paths = (
            sum(1 for vs in specs
                if any(arm.kind == "intervene" for arm in vs.spec.arms))
            >= 2
        ) or any(
            vs.spec.measurement.kind == "partial_correlation"
            for vs in specs
        )
        if not has_multiple_paths:
            issues.append({
                "severity": "warning",
                "check": "mediation_needs_paths",
                "message": (
                    "Text implies mediation analysis but specs don't compare "
                    "direct vs indirect paths (need multiple interventional "
                    "specs or partial correlations)."
                ),
            })

    # --- Check 6: Identifiability text → identifiability_check ---
    if _text_has_keyword(text, _IDENT_KEYWORDS):
        has_ident = any(
            vs.spec.measurement.kind == "identifiability_check"
            for vs in specs
        )
        if not has_ident:
            issues.append({
                "severity": "warning",
                "check": "ident_needs_check",
                "message": (
                    "Text implies identifiability concern but no spec uses "
                    "identifiability_check measurement."
                ),
            })

    return issues


# ---------------------------------------------------------------------------
# Answer key grounding: run specs against SCM, repair assertions, fill verdicts
# ---------------------------------------------------------------------------


@dataclass
class SQGroundingResult:
    """Result of grounding a compiled SQ against the SCM.

    The answer key is the RICH SCM result stored in each VerificationSpec.verdict
    (AtomVerdict.detail has measurements + comparison_result). NOT the Assertion.

    IMPORTANT: verdict.solver_assertion_holds reflects whether the LLM compiler's
    GUESSED assertion matched reality. It is NOT a validity gate for the answer key.
    A spec with holds=False still has a valid answer key in verdict.detail — it just
    means the compiler guessed wrong about the direction/type.
    """

    sq: SubQuestionIntentV2 | None  # with verdicts filled (None if all crashed)
    n_executed: int = 0   # specs that ran successfully against SCM
    n_crashed: int = 0    # specs that crashed during verify_atom
    warnings: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.sq is not None


def ground_sq_answer_key(
    sq: SubQuestionIntentV2,
    world: Any,
    solver: Any,
    seed: int = 42,
) -> SQGroundingResult:
    """Ground a compiled SQ against the SCM: run each spec and store the result.

    This is RESOLUTION, not evaluation. The answer key is the rich SCM result
    stored in each verdict.detail (measurements, comparison_result, ground_truth).
    The compiler's Assertion is left as-is — it's just the LLM's hypothesis,
    not the truth. The truth lives in the verdict.

    Only rejects specs that CRASH (can't execute). A spec whose assertion
    doesn't hold is still valid — it has a good answer key, the compiler
    just guessed wrong about the assertion.

    Args:
        seed: deterministic seed for verify_atom MC sampling. Critical for
              reproducible answer keys across runs (RL-safe).
    """
    from sreg.tools.oi_verifier import verify_atom

    grounded_specs: list[VerificationSpec] = []
    n_executed = 0
    n_crashed = 0
    warnings: list[str] = []

    for i, vs in enumerate(sq.verification_specs):
        spec_id = vs.spec.spec_id
        # Per-spec seed offset to avoid correlation between specs
        spec_seed = seed + i * 7919

        try:
            verdict = verify_atom(vs.spec, world, solver, seed=spec_seed)
        except Exception as e:
            warnings.append(f"{spec_id}: verify crash: {e}")
            n_crashed += 1
            continue

        n_executed += 1

        # Log diagnostic: did the compiler's assertion match reality?
        if not verdict.solver_assertion_holds:
            logger.info(
                "  %s: compiler assertion %s != ground truth (gt=%s) "
                "-- answer key is valid, assertion was wrong",
                spec_id,
                vs.spec.assertion.kind,
                verdict.ground_truth,
            )

        # Store spec with verdict (answer key = verdict.detail)
        grounded_specs.append(
            VerificationSpec(spec=vs.spec, role=vs.role, verdict=verdict)
        )

    if not grounded_specs:
        warnings.append("All specs crashed -- SQ cannot be grounded")
        return SQGroundingResult(
            sq=None,
            n_executed=n_executed,
            n_crashed=n_crashed,
            warnings=warnings,
        )

    grounded_sq = SubQuestionIntentV2(
        sq_id=sq.sq_id,
        text_gloss=sq.text_gloss,
        verification_specs=grounded_specs,
        tier=sq.tier,
        focus_variables=sq.focus_variables,
    )

    return SQGroundingResult(
        sq=grounded_sq,
        n_executed=n_executed,
        n_crashed=n_crashed,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Answer key view — normalized adapter for external consumers
# ---------------------------------------------------------------------------


def render_answer_key(verdict: AtomVerdict) -> dict[str, Any]:
    """Normalize verdict.detail into a stable view for external consumers.

    This is the ONLY function that should read verdict.detail.  All consumers
    (LLM judge, future deterministic matcher, diagnostics) go through here.

    Returns a dict with stable keys:
        result_type : str   — "difference", "ratio", "ranking", "gap",
                              "proportion", "changepoint", "contrast",
                              "scalar", "bool", "error", "empty", "unknown"
        value       : Any   — the main result (float, bool, list, dict)
        arms        : dict  — measurements per arm (ALWAYS from detail.measurements)
        headline    : str   — human-readable one-liner (for debug / display only)
        meta        : dict  — comparison_kind, measurement_kind, spec_id
        values      : dict  — (optional, ranking/gap only) labeled values from comparison
    """
    detail = verdict.detail
    spec = verdict.spec

    # -- Edge: error or empty detail --
    if "error" in detail:
        return {
            "result_type": "error",
            "value": None,
            "arms": {},
            "headline": f"error: {detail['error']}",
            "meta": _answer_key_meta(spec),
        }

    measurements = detail.get("measurements", {})
    comparison = detail.get("comparison", {})

    if not comparison:
        return {
            "result_type": "empty",
            "value": None,
            "arms": measurements,
            "headline": "no comparison result",
            "meta": _answer_key_meta(spec),
        }

    meta = _answer_key_meta(spec)
    arms = measurements

    # -- Dispatch by comparison keys (NOT by enum — works from the data) --

    if "ranking" in comparison:
        ranking = list(comparison["ranking"])
        values = comparison.get("values", {})
        parts = " > ".join(ranking)
        return {
            "result_type": "ranking",
            "value": ranking,
            "arms": arms,
            "values": values,
            "headline": f"ranking: {parts}",
            "meta": meta,
        }

    if "changepoint" in comparison:
        cp = comparison["changepoint"]
        if cp.get("detected"):
            cp_x = cp.get("changepoint_x", "?")
            cp_r = cp.get("reduction_fraction")
            hl = f"changepoint at x={cp_x}"
            if isinstance(cp_r, (int, float)):
                hl += f" (reduction={cp_r:.1%})"
        else:
            hl = "no changepoint detected"
        return {
            "result_type": "changepoint",
            "value": cp,
            "arms": arms,
            "headline": hl,
            "meta": meta,
        }

    if "contrast_diff" in comparison:
        cd = comparison["contrast_diff"]
        hl = f"contrast diff = {cd:+.4g}" if isinstance(cd, (int, float)) else "contrast diff = N/A"
        return {
            "result_type": "contrast",
            "value": cd,
            "arms": arms,
            "headline": hl,
            "meta": meta,
        }

    if "difference" in comparison:
        diff = comparison["difference"]
        ref = comparison.get("ref")
        other = comparison.get("other")
        hl = f"difference = {diff:+.4g}"
        if ref is not None and other is not None:
            hl += f" ({other:.4g} vs {ref:.4g})"
        return {
            "result_type": "difference",
            "value": diff,
            "arms": arms,
            "headline": hl,
            "meta": meta,
        }

    if "ratio" in comparison:
        r = comparison["ratio"]
        return {
            "result_type": "ratio",
            "value": r,
            "arms": arms,
            "headline": f"ratio = {r:.4g}",
            "meta": meta,
        }

    if "gap" in comparison:
        g = comparison["gap"]
        values = comparison.get("values", {})
        return {
            "result_type": "gap",
            "value": g,
            "arms": arms,
            "values": values,
            "headline": f"gap = {g:.4g}",
            "meta": meta,
        }

    if "proportion" in comparison:
        p = comparison["proportion"]
        return {
            "result_type": "proportion",
            "value": p,
            "arms": arms,
            "headline": f"proportion = {p:.4g}",
            "meta": meta,
        }

    if "value" in comparison:
        v = comparison["value"]
        if isinstance(v, bool):
            return {
                "result_type": "bool",
                "value": v,
                "arms": arms,
                "headline": str(v),
                "meta": meta,
            }
        return {
            "result_type": "scalar",
            "value": v,
            "arms": arms,
            "headline": f"value = {v}" if not isinstance(v, str) else v,
            "meta": meta,
        }

    # Fallback — unknown comparison structure
    logger.warning(
        "render_answer_key: unrecognized comparison keys %s for spec %s",
        list(comparison.keys()),
        spec.spec_id,
    )
    return {
        "result_type": "unknown",
        "value": comparison,
        "arms": arms,
        "headline": f"unknown comparison: {list(comparison.keys())}",
        "meta": meta,
    }


def _answer_key_meta(spec: AtomicSpec) -> dict[str, str]:
    """Extract stable metadata from the spec for traceability."""
    return {
        "spec_id": spec.spec_id,
        "comparison_kind": spec.comparison.kind.value if spec.comparison else "",
        "measurement_kind": spec.measurement.kind.value if spec.measurement else "",
    }
