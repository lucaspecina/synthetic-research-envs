"""OI Compiler: translate solver ClaimCards to verifiable AtomicSpecs.

Architecture (from Codex debate):
    ClaimCard (NL) → [LLM] → ClaimIntent (symbolic IR) → [deterministic] → AtomicSpec(s)

The LLM's job is ONLY to extract intent (pattern, variable roles, direction).
The code fills in concrete values (percentiles, thresholds, arm labels) using
shared canonical anchors from WorldSummary. This confines subjectivity to the
smallest possible space.

This module implements:
1. ClaimIntent — intermediate symbolic representation
2. WorldSummary — canonical anchors (percentiles, bounds per variable)
3. lower_intent() — deterministic lowering from ClaimIntent to AtomicSpec(s)
4. validate_intent() — preview validator (deterministic, no LLM)

The LLM extraction (ClaimCard → ClaimIntent) is a separate module that
requires API access. This module is pure computation.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, model_validator

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    Comparison,
    ComparisonKind,
    EpisodeScore,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
    SalienceFamily,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WorldSummary — canonical anchors for each variable
# ---------------------------------------------------------------------------


class VariableAnchors(BaseModel):
    """Canonical percentile anchors for one variable."""

    name: str
    p25: float
    p50: float
    p75: float
    p90: float
    p10: float
    mean: float
    std: float
    is_observable: bool = True


class WorldSummary(BaseModel):
    """Pre-computed summary statistics for all variables in a world.

    Used by the compiler to translate vague phrases ("high", "above median")
    into concrete intervention/condition values. Computed ONCE per world,
    shared between salience map generator and compiler.
    """

    world_id: str
    target: str
    variables: dict[str, VariableAnchors]
    observable_names: list[str]

    def anchors(self, var: str) -> VariableAnchors:
        """Get anchors for a variable, raising ValueError if missing."""
        if var not in self.variables:
            raise ValueError(f"Variable '{var}' not in world summary")
        return self.variables[var]

    def hi(self, var: str) -> float:
        """Canonical 'high' value = p75."""
        return self.anchors(var).p75

    def lo(self, var: str) -> float:
        """Canonical 'low' value = p25."""
        return self.anchors(var).p25

    def mid(self, var: str) -> float:
        """Canonical 'median' = p50."""
        return self.anchors(var).p50


def build_world_summary(
    world: SCMWorld, target: str, n_mc: int = 50_000, seed: int = 42
) -> WorldSummary:
    """Build a WorldSummary from an SCMWorld."""
    df = world.sample(n=n_mc, seed=seed)
    obs = set(world.observable_variables)
    variables = {}

    for var in world.variables:
        if var not in df.columns:
            continue
        col = df[var].values
        variables[var] = VariableAnchors(
            name=var,
            p10=float(np.percentile(col, 10)),
            p25=float(np.percentile(col, 25)),
            p50=float(np.percentile(col, 50)),
            p75=float(np.percentile(col, 75)),
            p90=float(np.percentile(col, 90)),
            mean=float(np.mean(col)),
            std=float(max(np.std(col), 1e-6)),
            is_observable=var in obs,
        )

    return WorldSummary(
        world_id=world.id,
        target=target,
        variables=variables,
        observable_names=sorted(obs),
    )


# ---------------------------------------------------------------------------
# ClaimIntent — symbolic intermediate representation
# ---------------------------------------------------------------------------


class PatternClass(StrEnum):
    """Recognized claim patterns the compiler can translate."""

    CAUSAL_EFFECT = "causal_effect"
    MEDIATION = "mediation"
    HETEROGENEITY = "heterogeneity"
    TAIL_RISK = "tail_risk"
    VARIANCE_EFFECT = "variance_effect"
    OBSERVATIONAL_ASSOCIATION = "observational_association"
    EFFECT_RANKING = "effect_ranking"


class Direction(StrEnum):
    """Asserted direction of an effect."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEAR_ZERO = "near_zero"


class ClaimIntent(BaseModel):
    """Symbolic intent extracted from a ClaimCard by the LLM.

    This is the IR between natural language and formal spec. The LLM fills
    in pattern_class, variable roles, and direction. The code fills in
    concrete values via WorldSummary.
    """

    claim_id: str = Field(min_length=1)
    pattern: PatternClass
    treatment: str = Field(min_length=1, description="Main cause variable")
    outcome: str = Field(min_length=1, description="Main outcome variable")
    direction: Direction = Direction.POSITIVE

    # Optional role-specific fields
    mediator: str | None = Field(default=None, description="For mediation: X→M→Y")
    modifier: str | None = Field(default=None, description="For heterogeneity: effect varies by Z")
    ranking_vars: list[str] = Field(
        default_factory=list, description="For ranking: which vars to compare"
    )
    conditioning_set: list[str] = Field(
        default_factory=list, description="For observational: control variables"
    )

    # Scope
    scope: Literal["global", "conditional"] = "global"
    evidence_type: Literal["interventional", "observational"] = "interventional"

    @model_validator(mode="after")
    def validate_roles(self) -> ClaimIntent:
        """Check pattern-specific role requirements."""
        if self.pattern == PatternClass.MEDIATION and not self.mediator:
            raise ValueError("Mediation pattern requires mediator variable")
        if self.pattern == PatternClass.HETEROGENEITY and not self.modifier:
            raise ValueError("Heterogeneity pattern requires modifier variable")
        if self.pattern == PatternClass.EFFECT_RANKING and len(self.ranking_vars) < 2:
            raise ValueError("Effect ranking requires at least 2 variables to compare")
        if self.pattern == PatternClass.OBSERVATIONAL_ASSOCIATION:
            if self.evidence_type != "observational":
                object.__setattr__(self, "evidence_type", "observational")
        return self


# ---------------------------------------------------------------------------
# CompilerOutput — result of compiling one ClaimCard
# ---------------------------------------------------------------------------


class CompilerOutput(BaseModel):
    """Result of compiling one ClaimCard."""

    claim_id: str
    status: Literal["compiled", "abstention"] = "compiled"
    specs: list[AtomicSpec] = Field(default_factory=list)
    abstention_reason: str | None = None

    @property
    def compiled(self) -> bool:
        return self.status == "compiled" and len(self.specs) > 0


# ---------------------------------------------------------------------------
# Intent validation (deterministic preview)
# ---------------------------------------------------------------------------


def validate_intent(intent: ClaimIntent, summary: WorldSummary) -> list[str]:
    """Validate a ClaimIntent against a WorldSummary.

    Returns list of error messages. Empty = valid.
    """
    errors: list[str] = []
    obs = set(summary.observable_names)

    # Check treatment exists and is observable
    if intent.treatment not in summary.variables:
        errors.append(f"Treatment '{intent.treatment}' not in world variables")
    elif intent.treatment not in obs:
        errors.append(f"Treatment '{intent.treatment}' is not observable")

    # Check outcome exists and is observable
    if intent.outcome not in summary.variables:
        errors.append(f"Outcome '{intent.outcome}' not in world variables")
    elif intent.outcome not in obs:
        errors.append(f"Outcome '{intent.outcome}' is not observable")

    # Check mediator
    if intent.mediator:
        if intent.mediator not in summary.variables:
            errors.append(f"Mediator '{intent.mediator}' not in world variables")
        elif intent.mediator not in obs:
            errors.append(f"Mediator '{intent.mediator}' is not observable")

    # Check modifier
    if intent.modifier:
        if intent.modifier not in summary.variables:
            errors.append(f"Modifier '{intent.modifier}' not in world variables")
        elif intent.modifier not in obs:
            errors.append(f"Modifier '{intent.modifier}' is not observable")

    # Check ranking vars
    for v in intent.ranking_vars:
        if v not in summary.variables:
            errors.append(f"Ranking variable '{v}' not in world variables")

    # Check conditioning set
    for v in intent.conditioning_set:
        if v not in summary.variables:
            errors.append(f"Conditioning variable '{v}' not in world variables")

    # Check treatment != outcome
    if intent.treatment == intent.outcome:
        errors.append("Treatment and outcome must be different variables")

    return errors


# ---------------------------------------------------------------------------
# Deterministic lowering: ClaimIntent → AtomicSpec(s)
# ---------------------------------------------------------------------------

_DIRECTION_MAP: dict[Direction, AssertionKind] = {
    Direction.POSITIVE: AssertionKind.POSITIVE,
    Direction.NEGATIVE: AssertionKind.NEGATIVE,
    Direction.NEAR_ZERO: AssertionKind.NEAR_ZERO,
}


def lower_intent(intent: ClaimIntent, summary: WorldSummary) -> CompilerOutput:
    """Lower a validated ClaimIntent to one or more AtomicSpecs.

    Uses canonical anchors from WorldSummary for intervention values.
    Returns CompilerOutput with specs or abstention.
    """
    errors = validate_intent(intent, summary)
    if errors:
        return CompilerOutput(
            claim_id=intent.claim_id,
            status="abstention",
            abstention_reason=f"Validation failed: {'; '.join(errors)}",
        )

    try:
        if intent.pattern == PatternClass.CAUSAL_EFFECT:
            specs = _lower_causal_effect(intent, summary)
        elif intent.pattern == PatternClass.MEDIATION:
            specs = _lower_mediation(intent, summary)
        elif intent.pattern == PatternClass.HETEROGENEITY:
            specs = _lower_heterogeneity(intent, summary)
        elif intent.pattern == PatternClass.TAIL_RISK:
            specs = _lower_tail_risk(intent, summary)
        elif intent.pattern == PatternClass.VARIANCE_EFFECT:
            specs = _lower_variance_effect(intent, summary)
        elif intent.pattern == PatternClass.OBSERVATIONAL_ASSOCIATION:
            specs = _lower_observational(intent, summary)
        elif intent.pattern == PatternClass.EFFECT_RANKING:
            specs = _lower_ranking(intent, summary)
        else:
            return CompilerOutput(
                claim_id=intent.claim_id,
                status="abstention",
                abstention_reason=f"Unknown pattern: {intent.pattern}",
            )
    except Exception as e:
        logger.warning("Lowering failed for %s: %s", intent.claim_id, e)
        return CompilerOutput(
            claim_id=intent.claim_id,
            status="abstention",
            abstention_reason=f"Lowering error: {e}",
        )

    return CompilerOutput(claim_id=intent.claim_id, specs=specs)


def _lower_causal_effect(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower causal effect: do(X=hi) vs do(X=lo), measure mean(Y)."""
    x, y = intent.treatment, intent.outcome
    return [
        AtomicSpec(
            spec_id=f"compiled_ate_{x}_{y}",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
            ),
            measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
        )
    ]


def _lower_mediation(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower mediation: two specs — ATE + indirect effect via mediator.

    Per Codex recommendation: multi-part claims → separate specs.
    Spec 1: ATE (X→Y total effect)
    Spec 2: Indirect effect (total - controlled direct, holding M at reference)
    """
    x, y, m = intent.treatment, intent.outcome, intent.mediator
    assert m is not None  # validated by ClaimIntent

    ate_spec = AtomicSpec(
        spec_id=f"compiled_ate_{x}_{y}",
        arms=(
            QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
            QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
        ),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
        comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
        assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
    )

    # m_ref = median of M (canonical reference)
    m_ref = summary.mid(m)
    indirect_spec = AtomicSpec(
        spec_id=f"compiled_med_{x}_{m}_{y}",
        arms=(
            QueryArm(label="total_hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
            QueryArm(label="total_lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
            QueryArm(
                label="direct_hi",
                kind=QueryKind.INTERVENE,
                values={x: summary.hi(x), m: m_ref},
            ),
            QueryArm(
                label="direct_lo",
                kind=QueryKind.INTERVENE,
                values={x: summary.lo(x), m: m_ref},
            ),
        ),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
        comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
        assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
    )

    return [ate_spec, indirect_spec]


def _lower_heterogeneity(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower heterogeneity: ATE + interaction (ATE differs by modifier strata).

    Per Codex: multi-part → 2 specs.
    Spec 1: ATE exists
    Spec 2: ATE differs across modifier strata (CONTRAST_DIFF → SIGN_FLIP)
    """
    x, y, z = intent.treatment, intent.outcome, intent.modifier
    assert z is not None  # validated by ClaimIntent

    ate_spec = AtomicSpec(
        spec_id=f"compiled_ate_{x}_{y}",
        arms=(
            QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
            QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
        ),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
        comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
        assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
    )

    het_spec = AtomicSpec(
        spec_id=f"compiled_het_{x}_{z}_{y}",
        arms=(
            QueryArm(
                label="hi_zhi",
                kind=QueryKind.INTERVENE,
                values={x: summary.hi(x)},
                condition_on={z: summary.hi(z)},
            ),
            QueryArm(
                label="lo_zhi",
                kind=QueryKind.INTERVENE,
                values={x: summary.lo(x)},
                condition_on={z: summary.hi(z)},
            ),
            QueryArm(
                label="hi_zlo",
                kind=QueryKind.INTERVENE,
                values={x: summary.hi(x)},
                condition_on={z: summary.lo(z)},
            ),
            QueryArm(
                label="lo_zlo",
                kind=QueryKind.INTERVENE,
                values={x: summary.lo(x)},
                condition_on={z: summary.lo(z)},
            ),
        ),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
        comparison=Comparison(kind=ComparisonKind.CONTRAST_DIFF),
        assertion=Assertion(kind=AssertionKind.SIGN_FLIP, tolerance=0.05),
    )

    return [ate_spec, het_spec]


def _lower_tail_risk(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower tail risk: do(X=hi) vs do(X=lo), measure P(Y > p90)."""
    x, y = intent.treatment, intent.outcome
    return [
        AtomicSpec(
            spec_id=f"compiled_tail_{x}_{y}",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
            ),
            measurement=Measurement(
                kind=MeasurementKind.TAIL_PROB,
                target=y,
                threshold=summary.anchors(y).p90,
            ),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
        )
    ]


def _lower_variance_effect(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower variance effect: do(X=hi) vs do(X=lo), measure Var(Y)."""
    x, y = intent.treatment, intent.outcome
    return [
        AtomicSpec(
            spec_id=f"compiled_var_{x}_{y}",
            arms=(
                QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
                QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
            ),
            measurement=Measurement(kind=MeasurementKind.VARIANCE, target=y),
            comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
            assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
        )
    ]


def _lower_observational(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower observational association: partial correlation."""
    x, y = intent.treatment, intent.outcome
    cond = tuple(intent.conditioning_set[:3])
    return [
        AtomicSpec(
            spec_id=f"compiled_pcor_{x}_{y}",
            arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
            measurement=Measurement(
                kind=MeasurementKind.PARTIAL_CORRELATION,
                lhs=x,
                rhs=y,
                cond_set=cond,
            ),
            comparison=Comparison(kind=ComparisonKind.IDENTITY),
            assertion=Assertion(kind=_DIRECTION_MAP[intent.direction]),
        )
    ]


def _lower_ranking(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower effect ranking: compare ATE of several variables on outcome."""
    y = intent.outcome
    rank_vars = intent.ranking_vars[:3]

    arms = tuple(
        QueryArm(
            label=f"ate_{v}",
            kind=QueryKind.INTERVENE,
            values={v: summary.hi(v)},
        )
        for v in rank_vars
    )

    return [
        AtomicSpec(
            spec_id=f"compiled_rank_{'_'.join(rank_vars)}_{y}",
            arms=arms,
            measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
            comparison=Comparison(kind=ComparisonKind.RANKING),
            assertion=Assertion(
                kind=AssertionKind.RANK_ORDER,
                order=tuple(f"ate_{v}" for v in rank_vars),
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Matching: compiled specs → salience families
# ---------------------------------------------------------------------------


def _extract_focus_signature(spec: AtomicSpec) -> tuple[str, ...]:
    """Extract focus variable signature from a compiled spec."""
    variables: set[str] = set()
    # From arms: intervention/condition variables
    for arm in spec.arms:
        variables.update(arm.values.keys())
        variables.update(arm.condition_on.keys())
    # From measurement: target, lhs, rhs
    if spec.measurement.target:
        if isinstance(spec.measurement.target, str):
            variables.add(spec.measurement.target)
        elif isinstance(spec.measurement.target, tuple):
            variables.update(spec.measurement.target)
    if spec.measurement.lhs:
        variables.add(spec.measurement.lhs)
    if spec.measurement.rhs:
        variables.add(spec.measurement.rhs)
    return tuple(sorted(variables))


def _infer_pattern_class(spec: AtomicSpec) -> str:
    """Infer pattern class from spec structure."""
    m = spec.measurement.kind
    c = spec.comparison.kind

    if m == MeasurementKind.PARTIAL_CORRELATION:
        return "observational_association"
    if m == MeasurementKind.VARIANCE:
        return "variance_effect"
    if m == MeasurementKind.TAIL_PROB:
        return "tail_risk"
    if c == ComparisonKind.RANKING:
        return "effect_ranking"
    if c == ComparisonKind.CONTRAST_DIFF:
        # 4 arms → mediation or heterogeneity
        # Check if assertion is SIGN_FLIP → heterogeneity
        if spec.assertion.kind == AssertionKind.SIGN_FLIP:
            return "heterogeneity"
        return "mediation"
    if c == ComparisonKind.DIFFERENCE:
        return "causal_effect"
    return "causal_effect"


def match_specs_to_families(
    compiled_specs: list[AtomicSpec],
    families: list[SalienceFamily],
) -> list[tuple[str | None, AtomicSpec]]:
    """Match compiled specs to the best salience family.

    Returns list of (matched_family_id or None, spec) pairs.
    Matching is deterministic: focus_signature overlap + pattern_class compatibility.
    """

    matches: list[tuple[str | None, AtomicSpec]] = []

    for spec in compiled_specs:
        focus_sig = set(_extract_focus_signature(spec))
        pattern = _infer_pattern_class(spec)

        best_family_id: str | None = None
        best_score = 0.0

        for family in families:
            # Pattern class compatibility
            family_pattern = family.key.pattern_class
            pattern_match = 1.0 if pattern == family_pattern else 0.0

            # Focus signature overlap (Jaccard similarity)
            family_focus = set(family.key.focus_signature)
            intersection = len(focus_sig & family_focus)
            union = len(focus_sig | family_focus)
            focus_overlap = intersection / max(union, 1)

            # Combined matching score: pattern must match, focus is bonus
            match_score = pattern_match * (0.5 + 0.5 * focus_overlap)

            if match_score > best_score:
                best_score = match_score
                best_family_id = family.family_id

        matches.append((best_family_id if best_score > 0 else None, spec))

    return matches


def score_compiled_episode(
    compiled_claims: list[CompilerOutput],
    families: list[SalienceFamily],
    world: SCMWorld,
    solver: SCMSolver,
    n_mc: int = 50_000,
    seed: int | None = None,
) -> EpisodeScore:
    """Score a full episode: compile → verify → match → score.

    This is the main entry point for scoring compiled claims.
    Handles abstentions per Codex design: abstention gets 0 correctness,
    doesn't contribute to coverage, counts toward efficiency.
    """
    from sreg.tools.oi_verifier import score_episode, verify_atom

    claim_matches: list[tuple[str, float]] = []
    n_claims_submitted = len(compiled_claims)
    n_abstentions = 0

    for claim_output in compiled_claims:
        if not claim_output.compiled:
            # Abstention: 0 correctness, no family match
            n_abstentions += 1
            claim_matches.append(("__abstention__", 0.0))
            continue

        # Match each compiled spec to families
        matched = match_specs_to_families(claim_output.specs, families)

        for family_id, spec in matched:
            if family_id is None:
                # No family match: claim is irrelevant (verifiable but not salient)
                claim_matches.append(("__unmatched__", 0.0))
                continue

            # Verify the spec against the SCM
            verdict = verify_atom(spec, world, solver, n_mc=n_mc, seed=seed)
            claim_matches.append((family_id, verdict.score))

    # Score using existing episode scorer
    episode = score_episode(
        claim_matches=claim_matches,
        families=families,
        n_claims=n_claims_submitted,
    )

    return episode


__all__ = [
    "ClaimIntent",
    "CompilerOutput",
    "Direction",
    "PatternClass",
    "VariableAnchors",
    "WorldSummary",
    "build_world_summary",
    "lower_intent",
    "match_specs_to_families",
    "score_compiled_episode",
    "validate_intent",
]
