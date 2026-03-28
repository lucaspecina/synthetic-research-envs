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
    DESCRIPTIVE_PENALTY,
    NON_TARGET_CAP,
    RELEVANCE_ANCESTOR,
    RELEVANCE_DESCENDANT,
    Assertion,
    AssertionKind,
    AtomicSpec,
    ClaimCard,
    ClaimVerdict,
    Comparison,
    ComparisonKind,
    EpisodeScore,
    EpisodeTrace,
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


class CompilerOutput(BaseModel):
    """Result of compiling one ClaimCard."""

    claim_id: str
    status: Literal["compiled", "abstention"] = "compiled"
    specs: list[AtomicSpec] = Field(default_factory=list)
    abstention_reason: str | None = None
    intent: ClaimIntent | None = Field(
        default=None, description="Preserved ClaimIntent for sub-question scoring"
    )

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

    return CompilerOutput(claim_id=intent.claim_id, specs=specs, intent=intent)


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
    claim_cards: list[ClaimCard] | None = None,
    trace: EpisodeTrace | None = None,
    data_asset_ids: set[str] | None = None,
) -> EpisodeScore:
    """Score a full episode: compile → verify → match → warrant → score.

    This is the main entry point for scoring compiled claims.
    Handles abstentions per Codex design: abstention gets 0 correctness,
    doesn't contribute to coverage, counts toward efficiency.

    When claim_cards + trace + data_asset_ids are provided, evidence
    warrant is applied: each claim's truth score is multiplied by its
    warrant score. Multi-spec claims (mediation → 2 specs) get the same
    warrant for all their specs.

    Args:
        compiled_claims: Compiled ClaimIntents (from compiler pipeline).
        families: Salience map families for coverage scoring.
        world: The SCMWorld for verification.
        solver: SCMSolver for Monte Carlo verification.
        n_mc: Monte Carlo sample count.
        seed: Random seed.
        claim_cards: Original ClaimCards (for warrant). Must align 1:1
            with compiled_claims by claim_id.
        trace: EpisodeTrace from solver's investigation (for warrant).
        data_asset_ids: Valid artifact IDs in the problem (for warrant).
    """
    from sreg.tools.oi_verifier import score_episode, verify_atom
    from sreg.tools.oi_warrant import compute_episode_warrants

    claim_matches: list[tuple[str, float]] = []
    warrant_per_match: list[float] = []
    n_claims_submitted = len(compiled_claims)

    # Build warrant scores per claim if trace available
    claim_warrant_map: dict[str, float] = {}
    if claim_cards is not None and trace is not None and data_asset_ids is not None:
        # Build focus vars from compiled specs for more precise warrant
        focus_vars_per_claim: dict[str, set[str]] = {}
        for co in compiled_claims:
            if co.compiled:
                fvars: set[str] = set()
                for spec in co.specs:
                    fvars.update(_extract_focus_signature(spec))
                focus_vars_per_claim[co.claim_id] = fvars

        warrants = compute_episode_warrants(
            claim_cards, data_asset_ids, trace, focus_vars_per_claim
        )
        if warrants is not None:
            for card, w in zip(claim_cards, warrants):
                claim_warrant_map[card.claim_id] = w

    warrant_active = bool(claim_warrant_map)

    for claim_output in compiled_claims:
        claim_warrant = claim_warrant_map.get(claim_output.claim_id, 1.0)

        if not claim_output.compiled:
            # Abstention: 0 correctness, no family match
            claim_matches.append(("__abstention__", 0.0))
            warrant_per_match.append(claim_warrant)
            continue

        # Match each compiled spec to families
        matched = match_specs_to_families(claim_output.specs, families)

        for family_id, spec in matched:
            if family_id is None:
                claim_matches.append(("__unmatched__", 0.0))
                warrant_per_match.append(claim_warrant)
                continue

            # Verify the spec against the SCM
            verdict = verify_atom(spec, world, solver, n_mc=n_mc, seed=seed)
            claim_matches.append((family_id, verdict.score))
            # Same warrant for all specs from this claim
            warrant_per_match.append(claim_warrant)

    # Score using episode scorer with optional warrant
    episode = score_episode(
        claim_matches=claim_matches,
        families=families,
        n_claims=n_claims_submitted,
        warrant_scores=warrant_per_match if warrant_active else None,
    )

    return episode


# ---------------------------------------------------------------------------
# v2 Scoring: decouple correctness from family match
# ---------------------------------------------------------------------------


def _is_descriptive_spec(spec: AtomicSpec) -> bool:
    """Check if a spec is a trivial descriptive observation (no comparison)."""
    descriptive_measurements = {
        MeasurementKind.MEAN,
        MeasurementKind.VARIANCE,
        MeasurementKind.QUANTILE,
        MeasurementKind.DISTRIBUTION,
    }
    identity_comparisons = {ComparisonKind.IDENTITY, ComparisonKind.GAP}
    return (
        spec.measurement.kind in descriptive_measurements
        and spec.comparison.kind in identity_comparisons
    )


def compute_structural_relevance(
    focus_vars: set[str],
    target: str,
    dag: nx.DiGraph,
) -> float:
    """Compute structural relevance of a claim to the brief target.

    Uses DAG structure only — no LLM, fully deterministic.

    Relevance tiers:
    - 1.0: claim directly involves the target
    - 0.7: claim touches ancestors (causes) of the target
    - 0.4: claim touches descendants (effects) of the target
    - 0.0: claim touches nothing in target's causal neighbourhood

    Guardrails:
    - NON_TARGET_CAP: max relevance when target not in focus
    - Coverage penalty: vars outside causal neighbourhood dilute relevance
    """
    if not focus_vars:
        return 0.0

    ancestors = nx.ancestors(dag, target) if target in dag else set()
    descendants = nx.descendants(dag, target) if target in dag else set()
    relevant_vars = ancestors | descendants | {target}

    # Base relevance tier
    if target in focus_vars:
        base = 1.0
    elif focus_vars & ancestors:
        base = RELEVANCE_ANCESTOR
    elif focus_vars & descendants:
        base = RELEVANCE_DESCENDANT
    else:
        return 0.0

    # Coverage: penalize claims that mix relevant and irrelevant variables
    relevant_count = len(focus_vars & relevant_vars)
    coverage = relevant_count / len(focus_vars)

    relevance = base * coverage

    # Guardrail: cap when target not directly in focus
    if target not in focus_vars:
        relevance = min(relevance, NON_TARGET_CAP)

    return relevance


def score_compiled_episode_v2(
    compiled_claims: list[CompilerOutput],
    families: list[SalienceFamily],
    world: SCMWorld,
    solver: SCMSolver,
    target: str,
    n_mc: int = 50_000,
    seed: int | None = None,
    claim_cards: list[ClaimCard] | None = None,
    trace: EpisodeTrace | None = None,
    data_asset_ids: set[str] | None = None,
) -> EpisodeScore:
    """Score a full episode with v2 scoring: truth decoupled from family match.

    Key differences from v1:
    - Correctness comes from SCM verification alone (no family match gate)
    - Structural relevance weights each claim by proximity to target
    - Coverage is separate: only depends on family matching
    - Scoring is per-claim (not per-spec) using min() for multi-spec
    - Descriptive claims without target get additional penalty
    """
    from sreg.tools.oi_verifier import score_episode_v2, verify_atom
    from sreg.tools.oi_warrant import compute_episode_warrants

    n_claims_submitted = len(compiled_claims)
    dag = world.dag

    # Build warrant scores per claim if trace available
    claim_warrant_map: dict[str, float] = {}
    if claim_cards is not None and trace is not None and data_asset_ids is not None:
        focus_vars_per_claim: dict[str, set[str]] = {}
        for co in compiled_claims:
            if co.compiled:
                fvars: set[str] = set()
                for spec in co.specs:
                    fvars.update(_extract_focus_signature(spec))
                focus_vars_per_claim[co.claim_id] = fvars

        warrants = compute_episode_warrants(
            claim_cards, data_asset_ids, trace, focus_vars_per_claim
        )
        if warrants is not None:
            for card, w in zip(claim_cards, warrants):
                claim_warrant_map[card.claim_id] = w

    # Process each claim
    claim_verdicts: list[ClaimVerdict] = []

    for claim_output in compiled_claims:
        claim_warrant = claim_warrant_map.get(claim_output.claim_id, 1.0)

        if not claim_output.compiled:
            # Abstention: 0 truth, 0 relevance
            claim_verdicts.append(ClaimVerdict(
                claim_id=claim_output.claim_id,
                matched_family_id=None,
                truth_score=0.0,
                relevance=0.0,
                effective_score=0.0,
                score=0.0,
                verdict="abstention",
            ))
            continue

        # 1. Verify each spec against SCM → truth scores
        spec_truths: list[float] = []
        atom_verdicts = []
        for spec in claim_output.specs:
            verdict = verify_atom(spec, world, solver, n_mc=n_mc, seed=seed)
            spec_truths.append(verdict.score)
            atom_verdicts.append(verdict)

        # Per-claim truth: min (conjunction) for multi-spec claims
        truth = min(spec_truths) if spec_truths else 0.0

        # 2. Structural relevance (DAG-based)
        focus_vars = set()
        for spec in claim_output.specs:
            focus_vars.update(_extract_focus_signature(spec))
        relevance = compute_structural_relevance(focus_vars, target, dag)

        # Guardrail: descriptive penalty for trivial observations
        if target not in focus_vars and all(
            _is_descriptive_spec(s) for s in claim_output.specs
        ):
            relevance *= DESCRIPTIVE_PENALTY

        # 3. Family matching (for coverage only — uses match quality, not truth)
        matched = match_specs_to_families(claim_output.specs, families)
        best_family_id: str | None = None
        best_match_quality = 0.0
        for fam_id, spec in matched:
            if fam_id is not None:
                # Re-compute match score to pick best family by match quality
                focus_sig = set(_extract_focus_signature(spec))
                for family in families:
                    if family.family_id == fam_id:
                        family_focus = set(family.key.focus_signature)
                        overlap = len(focus_sig & family_focus) / max(
                            len(focus_sig | family_focus), 1
                        )
                        match_q = 0.5 + 0.5 * overlap
                        if match_q > best_match_quality:
                            best_match_quality = match_q
                            best_family_id = fam_id
                        break

        # 4. Effective score: truth * relevance * warrant
        from sreg.models.open_investigation import WARRANT_PRIOR_FLOOR
        if claim_warrant_map:
            warrant_mult = WARRANT_PRIOR_FLOOR + (1.0 - WARRANT_PRIOR_FLOOR) * claim_warrant
        else:
            warrant_mult = 1.0
        effective = truth * relevance * warrant_mult

        # Determine verdict label
        if truth == 0.0:
            verdict_label = "false"
        elif truth == 1.0 and relevance >= 0.7:
            verdict_label = "fully_true"
        elif truth > 0.0 and relevance >= 0.4:
            verdict_label = "partially_true"
        else:
            verdict_label = "true_but_irrelevant"

        claim_verdicts.append(ClaimVerdict(
            claim_id=claim_output.claim_id,
            matched_family_id=best_family_id,
            atom_verdicts=atom_verdicts,
            truth_score=truth,
            relevance=relevance,
            effective_score=effective,
            score=effective,
            verdict=verdict_label,
        ))

    # Score episode using v2 scorer
    episode = score_episode_v2(
        claim_verdicts=claim_verdicts,
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
    "compute_structural_relevance",
    "lower_intent",
    "match_specs_to_families",
    "score_compiled_episode",
    "score_compiled_episode_v2",
    "validate_intent",
]
