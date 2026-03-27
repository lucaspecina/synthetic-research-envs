"""Open Investigation models: composable verification grammar for free-form research.

This module defines the DSL for verifying solver claims against an SCM.
The grammar has 4 composable pieces: QueryContext + Measurement + Comparison + Assertion.
Any valid combination is an AtomicSpec that the verifier can execute.

Design principles:
- Observational and interventional queries are first-class (Surgery 1)
- Specificity bonus + overclaim penalty prevent Goodhart-on-simplicity (Surgery 2)
- Salience map is brief-anchored, not exhaustive (Surgery 3)
- regression_coefficient is explicitly forbidden (model-dependent, not world truth)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Piece 1: QueryContext — what "experiment" to run on the SCM
# ---------------------------------------------------------------------------


class QueryKind(StrEnum):
    """Type of query against the SCM world."""

    BASELINE = "baseline"
    INTERVENE = "intervene"
    OBSERVE = "observe"
    CONDITION = "condition"
    ADJUST = "adjust"
    SWEEP = "sweep"


class QueryArm(BaseModel):
    """A single arm (scenario) in a verification spec."""

    label: str = Field(min_length=1)
    kind: QueryKind
    values: dict[str, float | int | str | bool] = Field(default_factory=dict)
    condition_on: dict[str, float | int | str | bool] = Field(default_factory=dict)
    treatment: str | None = None
    outcome: str | None = None
    adjust_set: tuple[str, ...] = ()
    observed_vars: frozenset[str] | None = None
    sweep_var: str | None = None
    sweep_values: tuple[float | int, ...] = ()
    sweep_base: QueryKind = QueryKind.INTERVENE


# ---------------------------------------------------------------------------
# Piece 2: Measurement — what to measure from the simulation
# ---------------------------------------------------------------------------


class MeasurementKind(StrEnum):
    """Type of measurement to extract from sampled data."""

    MEAN = "mean"
    VARIANCE = "variance"
    QUANTILE = "quantile"
    TAIL_PROB = "tail_prob"
    PROB = "prob"
    CORRELATION = "correlation"
    PARTIAL_CORRELATION = "partial_correlation"
    DISTRIBUTION = "distribution"
    IDENTIFIABILITY_CHECK = "identifiability_check"


class Measurement(BaseModel):
    """What to measure from the query results."""

    kind: MeasurementKind
    target: str | tuple[str, ...] | None = None
    target_value: float | int | str | bool | None = None
    q: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float | None = None
    lhs: str | None = None
    rhs: str | None = None
    cond_set: tuple[str, ...] = ()
    treatment: str | None = None
    outcome: str | None = None
    candidate_causes: tuple[str, ...] = ()
    candidate_adjust_set: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_kind_fields(self) -> Measurement:
        if self.kind == MeasurementKind.QUANTILE and self.q is None:
            raise ValueError("quantile measurement requires q")
        if self.kind == MeasurementKind.TAIL_PROB and self.threshold is None:
            raise ValueError("tail_prob measurement requires threshold")
        if self.kind == MeasurementKind.PARTIAL_CORRELATION:
            if self.lhs is None or self.rhs is None:
                raise ValueError("partial_correlation requires lhs and rhs")
        if self.kind == MeasurementKind.IDENTIFIABILITY_CHECK:
            if self.treatment is None or self.outcome is None:
                raise ValueError("identifiability_check requires treatment and outcome")
        return self


# ---------------------------------------------------------------------------
# Piece 3: Comparison — how to relate measurements across arms
# ---------------------------------------------------------------------------


class ComparisonKind(StrEnum):
    """How to compare measurements across arms."""

    IDENTITY = "identity"
    DIFFERENCE = "difference"
    RATIO = "ratio"
    RANKING = "ranking"
    GAP = "gap"
    PROPORTION = "proportion"
    PIECEWISE_FIT = "piecewise_fit"
    CONTRAST_DIFF = "contrast_diff"


class Comparison(BaseModel):
    """How to compare results across query arms."""

    kind: ComparisonKind
    ref_arm: str | None = None
    order: tuple[str, ...] = ()
    tolerance: float = Field(default=0.05, ge=0.0)
    min_gap: float = Field(default=0.10, ge=0.0)


# ---------------------------------------------------------------------------
# Piece 4: Assertion — what should be true
# ---------------------------------------------------------------------------


class AssertionKind(StrEnum):
    """What the claim asserts about the comparison result."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEAR_ZERO = "near_zero"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    RANK_ORDER = "rank_order"
    CHANGEPOINT_EXISTS = "changepoint_exists"
    SIGN_FLIP = "sign_flip"
    GAP_MATERIAL = "gap_material"
    IDENTIFIABLE = "identifiable"
    NOT_IDENTIFIABLE = "not_identifiable"
    DISTINGUISHABLE = "distinguishable"
    NOT_DISTINGUISHABLE = "not_distinguishable"


class Assertion(BaseModel):
    """What the claim asserts should be true."""

    kind: AssertionKind
    threshold: float = 0.0
    tolerance: float = Field(default=0.05, ge=0.0)
    order: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# AtomicSpec — a single verifiable unit (combination of the 4 pieces)
# ---------------------------------------------------------------------------


class AtomicSpec(BaseModel):
    """A single verifiable atom: arms + measurement + comparison + assertion.

    This is the IR (intermediate representation) that the verifier executes
    against the SCM. Any claim can be decomposed into 1..N AtomicSpecs.
    """

    spec_id: str = Field(min_length=1)
    arms: tuple[QueryArm, ...] = Field(min_length=1)
    measurement: Measurement
    comparison: Comparison
    assertion: Assertion

    @model_validator(mode="after")
    def validate_arm_labels_unique(self) -> AtomicSpec:
        labels = [a.label for a in self.arms]
        if len(labels) != len(set(labels)):
            raise ValueError("arm labels must be unique")
        return self


# ---------------------------------------------------------------------------
# Claim Card — what the solver delivers
# ---------------------------------------------------------------------------


class EvidenceRef(BaseModel):
    """Reference to evidence the solver used to support a claim."""

    artifact_id: str = Field(min_length=1)
    rationale: str = Field(min_length=8, max_length=500)


class ClaimCard(BaseModel):
    """Semi-structured claim from the solver.

    The solver writes claim cards, not prose and not formal specs.
    This is a scientific reporting format, not a technical form.
    """

    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=15, max_length=800)
    focus_variables: list[str] = Field(min_length=1, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_basis: list[EvidenceRef] = Field(min_length=1, max_length=5)

    # Optional but improve compilation
    outcome_aspect: str | None = Field(default=None, max_length=200)
    comparison_text: str | None = Field(default=None, max_length=200)
    scope_text: str | None = Field(default=None, max_length=200)
    pattern_tags: list[str] = Field(default_factory=list, max_length=5)
    caveats: list[str] = Field(default_factory=list, max_length=3)


class ClaimSubmission(BaseModel):
    """The solver's final submission: 1..K claim cards."""

    claims: list[ClaimCard] = Field(min_length=1, max_length=5)

    @field_validator("claims")
    @classmethod
    def validate_unique_ids(cls, v: list[ClaimCard]) -> list[ClaimCard]:
        ids = [c.claim_id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("claim_id must be unique across claims")
        return v


# ---------------------------------------------------------------------------
# Salience Map — pre-computed truths for coverage scoring
# ---------------------------------------------------------------------------


class FamilyKey(BaseModel):
    """Canonical key for grouping equivalent claims into families."""

    brief_target: str
    focus_signature: tuple[str, ...] = Field(min_length=1)
    pattern_class: str
    scope_class: str = "global"

    @field_validator("focus_signature")
    @classmethod
    def validate_sorted(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(v))


class FamilyAtom(BaseModel):
    """A single verifiable truth within a family."""

    atom_id: str = Field(min_length=1)
    spec: AtomicSpec
    weight: float = Field(default=1.0, gt=0.0)
    material: bool = Field(
        default=True,
        description="If True, omitting this atom triggers overclaim penalty",
    )


class SalienceFamily(BaseModel):
    """A family of related truths in the salience map.

    Coverage is scored per-family, not per-atom.
    """

    family_id: str = Field(min_length=1)
    key: FamilyKey
    atoms: tuple[FamilyAtom, ...] = Field(min_length=1)
    salience: float = Field(gt=0.0, le=1.0)


class SalienceMap(BaseModel):
    """Brief-anchored map of discoverable truths for an SCM world.

    Typically 10-24 families for a 12-node SCM, hard cap at 30.
    """

    world_id: str
    brief_target: str
    families: list[SalienceFamily] = Field(max_length=30)

    @property
    def family_ids(self) -> set[str]:
        return {f.family_id for f in self.families}


# ---------------------------------------------------------------------------
# Scoring — verification results
# ---------------------------------------------------------------------------


class AtomVerdict(BaseModel):
    """Result of verifying a single AtomicSpec against the SCM."""

    atom_id: str
    spec: AtomicSpec
    ground_truth: float | bool | str | dict[str, Any]
    solver_assertion_holds: bool
    score: float = Field(ge=0.0, le=1.0)
    detail: dict[str, Any] = Field(default_factory=dict)


class ClaimVerdict(BaseModel):
    """Result of verifying a single claim against the salience map."""

    claim_id: str
    matched_family_id: str | None = None
    atom_verdicts: list[AtomVerdict] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0)
    verdict: str = Field(
        description="fully_true | partially_true_with_omission | mixed | false | unmatched"
    )


class EpisodeScore(BaseModel):
    """Complete scoring of an Open Investigation episode."""

    correctness: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    efficiency: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)
    claim_verdicts: list[ClaimVerdict] = Field(default_factory=list)
    families_hit: int = Field(ge=0)
    families_total: int = Field(ge=0)
    precision_gate_active: bool = False

    # Weights
    W_CORRECTNESS: float = 0.60
    W_COVERAGE: float = 0.30
    W_EFFICIENCY: float = 0.10


# ---------------------------------------------------------------------------
# Scoring parameters
# ---------------------------------------------------------------------------

SPEC_BASE: float = 0.50
SPEC_BONUS_MAX: float = 0.50
OVERCLAIM_MAX: float = 0.50
FAMILY_HIT_THRESHOLD: float = 0.60
EPISODE_PRECISION_GATE: float = 0.55
MAX_CLAIMS: int = 5
MAX_FAMILIES: int = 30


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "QueryKind",
    "QueryArm",
    "MeasurementKind",
    "Measurement",
    "ComparisonKind",
    "Comparison",
    "AssertionKind",
    "Assertion",
    "AtomicSpec",
    "EvidenceRef",
    "ClaimCard",
    "ClaimSubmission",
    "FamilyKey",
    "FamilyAtom",
    "SalienceFamily",
    "SalienceMap",
    "AtomVerdict",
    "ClaimVerdict",
    "EpisodeScore",
    "SPEC_BASE",
    "SPEC_BONUS_MAX",
    "OVERCLAIM_MAX",
    "FAMILY_HIT_THRESHOLD",
    "EPISODE_PRECISION_GATE",
    "MAX_CLAIMS",
    "MAX_FAMILIES",
]
