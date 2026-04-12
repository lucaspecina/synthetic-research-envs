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

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field, model_validator

from sreg.models.open_investigation import (
    Assertion,
    AssertionKind,
    AtomicSpec,
    ClaimCard,
    Comparison,
    ComparisonKind,
    Measurement,
    MeasurementKind,
    QueryArm,
    QueryKind,
)
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
    CONFOUNDING = "confounding"


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
    confounder: str | None = Field(
        default=None, description="For confounding: C confounds X→Y"
    )
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
        if self.pattern == PatternClass.CONFOUNDING and not self.confounder:
            raise ValueError("Confounding pattern requires confounder variable")
        return self


# ---------------------------------------------------------------------------
# CompilerOutput — result of compiling one ClaimCard
# ---------------------------------------------------------------------------


class CompiledUnit(BaseModel):
    """One verifiable unit extracted from a claim.

    Each unit has its own intent (the LLM-extracted symbolic IR) and specs
    (the deterministic lowering to AtomicSpecs). A compound claim produces
    N CompiledUnits; a simple claim produces 1.

    Backends:
    - "claim_intent": v1 — LLM extracts ClaimIntent IR, deterministic lowering
    - "grammar_direct": v2 — LLM produces AtomicSpecs directly from grammar
    """

    unit_id: str = Field(min_length=1)
    intent: ClaimIntent | None = None
    specs: list[AtomicSpec] = Field(default_factory=list)
    backend: Literal["claim_intent", "grammar_direct"] = "claim_intent"


class CompilerOutput(BaseModel):
    """Result of compiling one ClaimCard.

    1:1 with ClaimCard. May contain 0..N CompiledUnits. Multi-unit claims
    (A22) produce N units from compound assertions. Warranty, trace, and
    efficiency are keyed by claim_id (unchanged).
    """

    claim_id: str
    status: Literal["compiled", "partial", "abstention"] = "compiled"
    units: list[CompiledUnit] = Field(default_factory=list)
    abstention_reason: str | None = None
    uncompiled_fragments: list[str] = Field(
        default_factory=list, description="Fragments that could not be compiled"
    )

    @property
    def compiled(self) -> bool:
        return self.status in ("compiled", "partial") and len(self.units) > 0

    @property
    def specs(self) -> list[AtomicSpec]:
        """Flat list of all specs across units (backward compat)."""
        return [spec for u in self.units for spec in u.specs]

    @property
    def intents(self) -> list[ClaimIntent]:
        """All intents across units."""
        return [u.intent for u in self.units]

    @property
    def intent(self) -> ClaimIntent | None:
        """Single intent for backward compat. Returns first or None."""
        return self.units[0].intent if self.units else None


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

    # Check confounder
    if intent.confounder:
        if intent.confounder not in summary.variables:
            errors.append(f"Confounder '{intent.confounder}' not in world variables")
        elif intent.confounder not in obs:
            errors.append(f"Confounder '{intent.confounder}' is not observable")

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
        elif intent.pattern == PatternClass.CONFOUNDING:
            specs = _lower_confounding(intent, summary)
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

    unit = CompiledUnit(
        unit_id=intent.claim_id,
        intent=intent,
        specs=specs,
    )
    return CompilerOutput(claim_id=intent.claim_id, units=[unit])


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
        # #24 fix: direction-agnostic. For heterogeneity the point is
        # "effect varies across strata", not "pooled ATE is positive".
        # intent.direction is ambiguous (interaction vs pooled), so we
        # only check that a material ATE exists.
        assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
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


def _lower_confounding(intent: ClaimIntent, summary: WorldSummary) -> list[AtomicSpec]:
    """Lower confounding: verify that C confounds the X->Y relationship.

    Confounding means: the observational association between X and Y differs
    from the causal effect of X on Y. Controlling for confounders changes the
    relationship.

    Two specs (direction-agnostic — confounding is about the GAP existing,
    not about the sign of the effect):
    Spec 1: Causal ATE exists (non-zero, any direction). The causal effect
        must be material after removing confounding via do-calculus.
    Spec 2: Raw vs adjusted difference exists. The partial correlation
        after conditioning on C must be non-zero (the adjusted relationship).

    NOTE: We intentionally do NOT use the claim's direction for these specs.
    In Simpson's paradox, the crude association and the causal effect can have
    OPPOSITE signs. The confounding claim is about the GAP, not the direction.
    Using the claim's crude direction for the causal ATE would make ALL
    confounding claims in sign-reversal scenarios fail.
    """
    x, y, c = intent.treatment, intent.outcome, intent.confounder

    # Spec 1: Causal effect exists — direction-agnostic via GAP_MATERIAL
    # Confounding is about the GAP between crude and adjusted, not the
    # direction of the effect. Using the claim's direction would fail in
    # Simpson's paradox (crude and causal have opposite signs).
    spec_causal = AtomicSpec(
        spec_id=f"compiled_confound_causal_{x}_{y}_{c}",
        arms=(
            QueryArm(label="hi", kind=QueryKind.INTERVENE, values={x: summary.hi(x)}),
            QueryArm(label="lo", kind=QueryKind.INTERVENE, values={x: summary.lo(x)}),
        ),
        measurement=Measurement(kind=MeasurementKind.MEAN, target=y),
        comparison=Comparison(kind=ComparisonKind.DIFFERENCE, ref_arm="lo"),
        assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
    )

    # Spec 2: Adjusted partial correlation is non-zero (direction-agnostic)
    spec_partial = AtomicSpec(
        spec_id=f"compiled_confound_pcor_{x}_{y}_{c}",
        arms=(QueryArm(label="base", kind=QueryKind.BASELINE),),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs=x,
            rhs=y,
            cond_set=(c,),
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.GAP_MATERIAL),
    )

    return [spec_causal, spec_partial]


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
    # Check spec_id prefix for compiler-generated specs
    if spec.spec_id.startswith("confound_") or spec.spec_id.startswith("compiled_confound_"):
        return "confounding"

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
        # Check if arms have condition_on → may be confounding
        has_conditioning = any(
            arm.condition_on for arm in spec.arms
        )
        if has_conditioning:
            return "confounding"
        return "causal_effect"
    return "causal_effect"



__all__ = [
    "ClaimIntent",
    "CompiledUnit",
    "CompilerOutput",
    "Direction",
    "PatternClass",
    "VariableAnchors",
    "WorldSummary",
    "build_world_summary",
    "lower_intent",
    "validate_intent",
]
