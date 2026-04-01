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
from typing import Any, Literal

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
    focus_variables: list[str] = Field(min_length=1, max_length=12)
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
# Episode Trace — structured log of solver's investigation process
# ---------------------------------------------------------------------------


class ArtifactAccess(BaseModel):
    """Record of a solver accessing a data artifact during an episode."""

    artifact_id: str = Field(min_length=1)
    step: int = Field(ge=0, description="Episode step number")
    access_type: Literal["load", "inspect", "analyze"] = "load"


class AnalysisRecord(BaseModel):
    """Record of a solver running analysis code on data artifacts."""

    analysis_id: str = Field(min_length=1)
    input_artifact_ids: list[str] = Field(min_length=1)
    columns_used: list[str] = Field(default_factory=list)
    op_type: str = Field(
        min_length=1,
        description="Analysis type: describe, regression, correlation, groupby, plot, etc.",
    )
    step: int = Field(ge=0)
    output_artifact_id: str | None = Field(
        default=None, description="Derived artifact ID, if analysis produced one"
    )


class EpisodeTrace(BaseModel):
    """Structured trace of a solver's investigation during an OI episode.

    Used for evidence warrant checking: did the solver actually investigate
    to support its claims, or just submit from priors?
    """

    accesses: list[ArtifactAccess] = Field(default_factory=list)
    analyses: list[AnalysisRecord] = Field(default_factory=list)
    claim_steps: dict[str, int] = Field(
        default_factory=dict,
        description="claim_id -> step when claim was submitted",
    )

    def accessed_artifact_ids(self) -> set[str]:
        """All artifact IDs the solver accessed."""
        return {a.artifact_id for a in self.accesses}

    def analyzed_artifact_ids(self) -> set[str]:
        """All artifact IDs the solver ran analysis on."""
        ids: set[str] = set()
        for a in self.analyses:
            ids.update(a.input_artifact_ids)
        return ids

    def derived_artifact_ids(self) -> set[str]:
        """All artifact IDs created by solver analyses."""
        return {a.output_artifact_id for a in self.analyses if a.output_artifact_id}

    def columns_analyzed_for_artifact(self, artifact_id: str) -> set[str]:
        """Columns the solver analyzed for a specific artifact."""
        cols: set[str] = set()
        for a in self.analyses:
            if artifact_id in a.input_artifact_ids:
                cols.update(a.columns_used)
        return cols


class WarrantResult(BaseModel):
    """Per-claim evidence warrant assessment."""

    claim_id: str
    warrant_score: float = Field(ge=0.0, le=1.0)
    level_reached: int = Field(ge=0, le=3, description="Highest warrant level achieved")
    valid_refs: int = Field(ge=0, description="EvidenceRefs referencing real artifacts")
    accessed_refs: int = Field(ge=0, description="EvidenceRefs with accessed artifacts")
    analyzed_refs: int = Field(ge=0, description="EvidenceRefs with analyzed artifacts")


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
    """Result of verifying a single AtomicSpec against the SCM.

    The ``detail`` field is the **rich answer key** — the canonical truth
    artifact produced by the SCM.  It always contains two stable keys:

    - ``"measurements"``: ``dict[str, float | bool | dict]`` — one entry per
      arm label.  Value is ``float`` for most MeasurementKinds, ``bool`` for
      IDENTIFIABILITY_CHECK, ``dict[float, float]`` for SWEEP arms.
    - ``"comparison"``: ``dict[str, Any]`` — structure depends on
      ComparisonKind (see contract below).

    **COMPARISON CONTRACT** (stable keys by ComparisonKind):

    - IDENTITY:      ``{value: scalar}``
    - DIFFERENCE:    ``{difference: float, ref: float, other: float}``
    - RATIO:         ``{ratio: float}``
    - RANKING:       ``{ranking: tuple[str,...], values: dict[str,float]}``
    - GAP:           ``{gap: float, values: dict[str,float]}``
    - PROPORTION:    ``{proportion: float}``
    - PIECEWISE_FIT: ``{sweep_data: dict, changepoint: {detected: bool,
                       changepoint_x?: float, reduction_fraction?: float}}``
    - CONTRAST_DIFF: ``{contrast_diff: float}``

    **ASYMMETRY — teacher vs solver:**

    - For the **teacher** (SQ answer keys), ``detail`` IS the answer key.
      ``solver_assertion_holds`` only reflects whether the compiler's guessed
      Assertion matched reality — it is diagnostic, NOT a validity gate.
    - For the **solver** (claim verification), ``solver_assertion_holds`` is
      the core truth signal: did the solver's claim hold against the SCM?

    **FUTURE:** When multiple consumers need the rich answer key, promote
    ``detail`` to a formal ``AtomResolution`` model.  For now, consumers
    should use ``render_answer_key()`` (in ``oi_sq_compiler``) instead of
    reading ``detail`` directly.
    """

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
        description=(
            "v1: fully_true | partially_true_with_omission | mixed | false | unmatched. "
            "v2: fully_true | partially_true | true_but_irrelevant | false | abstention"
        )
    )

    # v2 scoring fields (populated by score_compiled_episode_v2)
    truth_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="SCM-verified truth score, independent of family match",
    )
    relevance: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Structural relevance to brief target (DAG-based)",
    )
    effective_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="truth * relevance * warrant (final per-claim score)",
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

    # Warrant diagnostics
    raw_correctness: float | None = Field(
        default=None, description="Correctness before warrant multiplier"
    )
    avg_warrant: float | None = Field(
        default=None, description="Mean warrant score across claims"
    )
    warrant_active: bool = Field(default=False, description="Whether warrant was applied")

    # Weights
    W_CORRECTNESS: float = 0.60
    W_COVERAGE: float = 0.30
    W_EFFICIENCY: float = 0.10


# ---------------------------------------------------------------------------
# Sub-Questions — orchestrator-generated investigation agenda
# ---------------------------------------------------------------------------


class AskOperator(StrEnum):
    """What the sub-question asks about the pattern."""

    EXISTENCE = "existence"
    SIGN = "sign"
    EXISTENCE_AND_SIGN = "existence_and_sign"
    MAGNITUDE = "magnitude"
    RANK_ORDER = "rank_order"


class AcceptanceRule(StrEnum):
    """How multiple claims can satisfy a sub-question."""

    ANY_OF = "any_of"
    ALL_OF = "all_of"


class SQTier(StrEnum):
    """Priority tier for sub-question weight assignment."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Tier -> weight mapping (deterministic, not LLM-assigned)
SQ_TIER_WEIGHTS: dict[str, float] = {
    "high": 1.0,
    "medium": 0.6,
    "low": 0.4,
}


class SQRoles(BaseModel):
    """Variable roles in a sub-question. Uses strings to avoid circular import."""

    treatment: str | None = None
    outcome: str | None = None
    mediator: str | None = None
    modifier: str | None = None
    confounder: str | None = None
    ranking_vars: tuple[str, ...] = ()
    conditioning_set: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_at_least_one(self) -> SQRoles:
        has_any = (
            self.treatment or self.outcome or self.mediator or self.modifier
            or self.confounder or self.ranking_vars
        )
        if not has_any:
            raise ValueError("SQRoles must specify at least one variable role")
        return self

    @property
    def focus_variables(self) -> frozenset[str]:
        """All variables involved in this sub-question."""
        vs: set[str] = set()
        if self.treatment:
            vs.add(self.treatment)
        if self.outcome:
            vs.add(self.outcome)
        if self.mediator:
            vs.add(self.mediator)
        if self.modifier:
            vs.add(self.modifier)
        if self.confounder:
            vs.add(self.confounder)
        vs.update(self.ranking_vars)
        return frozenset(vs)


class SubQuestionIntent(BaseModel):
    """What the orchestrator considers worth investigating.

    This is an investigation agenda item, NOT a claim/assertion.
    Pattern and direction use strings to avoid circular import with oi_compiler.
    Validated against PatternClass/Direction at the tools layer.
    """

    sq_id: str = Field(min_length=1)
    pattern: str = Field(description="Pattern class (causal_effect, mediation, etc.)")
    roles: SQRoles
    ask: AskOperator
    tier: SQTier = SQTier.HIGH
    materiality_threshold: float | None = Field(default=None, ge=0.0)
    text_gloss: str | None = None

    @property
    def weight(self) -> float:
        """Weight from tier mapping."""
        return SQ_TIER_WEIGHTS[self.tier.value]


class ResolvedAnswer(BaseModel):
    """Deterministic answer to a sub-question, resolved against the SCM."""

    exists: bool | None = None
    direction: str | None = Field(default=None, description="positive/negative/near_zero")
    magnitude: float | None = None
    effect_size: float | None = None
    rank_order: tuple[str, ...] = ()


class SQComponent(BaseModel):
    """A component of a multi-part sub-question.

    E.g., mediation SQ has: indirect effect component + total effect component.
    """

    component_id: str = Field(min_length=1)
    pattern: str
    roles: SQRoles
    ask: AskOperator
    contribution: float = Field(gt=0.0, le=1.0)
    resolved_answer: ResolvedAnswer
    resolved_specs: list[AtomicSpec] = Field(default_factory=list)


class ResolvedSubQuestion(BaseModel):
    """Sub-question with its deterministic resolution against the SCM.

    Built once when the world is instantiated. Used for scoring claims.
    """

    intent: SubQuestionIntent
    resolved_answer: ResolvedAnswer
    components: list[SQComponent] = Field(default_factory=list)
    acceptance_rule: AcceptanceRule = AcceptanceRule.ANY_OF
    resolution_evidence: dict[str, Any] = Field(default_factory=dict)
    salience_family_id: str | None = None

    @model_validator(mode="after")
    def validate_has_components(self) -> ResolvedSubQuestion:
        if not self.components:
            raise ValueError("ResolvedSubQuestion must have at least one component")
        return self


# ---------------------------------------------------------------------------
# Sub-Questions v2 — specs-based, no PatternClass
# ---------------------------------------------------------------------------


class VerificationSpec(BaseModel):
    """A single verification within a sub-question bundle.

    Each SQ carries 1..N of these. The role distinguishes obligatory
    verifications (required) from bonus evidence (support).
    """

    spec: AtomicSpec
    role: Literal["required", "support"] = "required"
    verdict: AtomVerdict | None = None


class SubQuestionIntentV2(BaseModel):
    """Specs-based sub-question — no PatternClass, no roles enum.

    The semantics are expressed entirely through the verification_specs bundle.
    text_gloss is free-form for human readability; it does NOT participate
    in matching or scoring.

    Coexists with SubQuestionIntent (v1) during migration.
    """

    sq_id: str = Field(min_length=1)
    text_gloss: str = Field(
        min_length=5,
        description="Free-form human-readable description of the investigation need",
    )
    verification_specs: list[VerificationSpec] = Field(min_length=1)
    tier: SQTier = SQTier.HIGH
    focus_variables: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_at_least_one_required(self) -> SubQuestionIntentV2:
        has_required = any(vs.role == "required" for vs in self.verification_specs)
        if not has_required:
            raise ValueError("SubQuestionIntentV2 must have at least one required spec")
        return self

    @property
    def weight(self) -> float:
        """Weight from tier mapping."""
        return SQ_TIER_WEIGHTS[self.tier.value]

    @property
    def required_specs(self) -> list[VerificationSpec]:
        return [vs for vs in self.verification_specs if vs.role == "required"]

    @property
    def support_specs(self) -> list[VerificationSpec]:
        return [vs for vs in self.verification_specs if vs.role == "support"]


class SubQuestionScore(BaseModel):
    """Per-sub-question scoring result."""

    sq_id: str
    satisfaction: float = Field(ge=0.0, le=1.0, description="How well claims cover this SQ")
    best_claim_id: str | None = None
    component_scores: dict[str, float] = Field(
        default_factory=dict,
        description="component_id -> best claim score for that component",
    )
    matched: bool = False


class EpisodeSubQuestionScore(BaseModel):
    """Episode-level scoring using sub-questions."""

    sq_scores: list[SubQuestionScore] = Field(default_factory=list)
    coverage: float = Field(ge=0.0, le=1.0, description="Fraction of SQs satisfied")
    weighted_coverage: float = Field(ge=0.0, le=1.0, description="Weight-adjusted coverage")
    correctness: float = Field(ge=0.0, le=1.0, description="Mean truth of matched claims")
    novel_bonus: float = Field(ge=0.0, le=0.2, description="Bonus for true findings outside SQs")
    total: float = Field(ge=0.0, le=1.0)


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
WARRANT_PRIOR_FLOOR: float = 0.15

# v2 scoring constants — structural relevance
NON_TARGET_CAP: float = 0.50  # max relevance when target not in focus
DESCRIPTIVE_PENALTY: float = 0.20  # multiplier for trivial descriptive claims
RELEVANCE_ANCESTOR: float = 0.70  # relevance for ancestor-touching claims
RELEVANCE_DESCENDANT: float = 0.40  # relevance for descendant-touching claims


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
    "ArtifactAccess",
    "AnalysisRecord",
    "EpisodeTrace",
    "WarrantResult",
    "FamilyKey",
    "FamilyAtom",
    "SalienceFamily",
    "SalienceMap",
    "AtomVerdict",
    "ClaimVerdict",
    "EpisodeScore",
    "AskOperator",
    "AcceptanceRule",
    "SQTier",
    "SQ_TIER_WEIGHTS",
    "SQRoles",
    "SubQuestionIntent",
    "ResolvedAnswer",
    "SQComponent",
    "ResolvedSubQuestion",
    "VerificationSpec",
    "SubQuestionIntentV2",
    "SubQuestionScore",
    "EpisodeSubQuestionScore",
    "SPEC_BASE",
    "SPEC_BONUS_MAX",
    "OVERCLAIM_MAX",
    "FAMILY_HIT_THRESHOLD",
    "EPISODE_PRECISION_GATE",
    "MAX_CLAIMS",
    "MAX_FAMILIES",
    "WARRANT_PRIOR_FLOOR",
    "NON_TARGET_CAP",
    "DESCRIPTIVE_PENALTY",
    "RELEVANCE_ANCESTOR",
    "RELEVANCE_DESCENDANT",
]
