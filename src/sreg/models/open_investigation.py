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
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Discriminator, Field, Tag, field_validator, model_validator

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


# ---------------------------------------------------------------------------
# Condition predicates — subpopulation filters for condition_on (P1)
# ---------------------------------------------------------------------------


class ApproxEq(BaseModel):
    """Match rows where variable is approximately equal to value (±tol_std * std)."""

    kind: Literal["approx_eq"] = "approx_eq"
    value: float | int
    tol_std: float = Field(default=0.15, ge=0.0)


class ConditionRange(BaseModel):
    """Match rows where lo <= variable <= hi."""

    kind: Literal["range"] = "range"
    lo: float
    hi: float

    @model_validator(mode="after")
    def _validate_order(self) -> "ConditionRange":
        if self.lo > self.hi:
            raise ValueError(f"range lo={self.lo} must be <= hi={self.hi}")
        return self


class QuantileRange(BaseModel):
    """Match rows in the given quantile range of the variable's distribution."""

    kind: Literal["quantile_range"] = "quantile_range"
    q_lo: float = Field(ge=0.0, le=1.0)
    q_hi: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_order(self) -> "QuantileRange":
        if self.q_lo > self.q_hi:
            raise ValueError(f"quantile_range q_lo={self.q_lo} must be <= q_hi={self.q_hi}")
        return self


class InSet(BaseModel):
    """Match rows where variable equals any of the listed values."""

    kind: Literal["in_set"] = "in_set"
    values: list[float | int | str | bool] = Field(min_length=1)


ConditionPredicate = Annotated[
    Union[
        Annotated[ApproxEq, Tag("approx_eq")],
        Annotated[ConditionRange, Tag("range")],
        Annotated[QuantileRange, Tag("quantile_range")],
        Annotated[InSet, Tag("in_set")],
    ],
    Discriminator("kind"),
]


class QueryArm(BaseModel):
    """A single arm (scenario) in a verification spec."""

    label: str = Field(min_length=1)
    kind: QueryKind
    values: dict[str, float | int | str | bool] = Field(default_factory=dict)
    condition_on: dict[str, ConditionPredicate] = Field(default_factory=dict)
    treatment: str | None = None
    outcome: str | None = None
    adjust_set: tuple[str, ...] = ()
    observed_vars: frozenset[str] | None = None
    sweep_var: str | None = None
    sweep_values: tuple[float | int, ...] = ()
    sweep_base: QueryKind = QueryKind.INTERVENE

    @model_validator(mode="before")
    @classmethod
    def _coerce_condition_on(cls, data: Any) -> Any:
        """Auto-promote raw scalars in condition_on to predicate objects."""
        if not isinstance(data, dict):
            return data
        co = data.get("condition_on")
        if not isinstance(co, dict):
            return data
        promoted: dict[str, Any] = {}
        for k, v in co.items():
            if isinstance(v, dict) and "kind" in v:
                promoted[k] = v  # already a predicate
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                promoted[k] = {"kind": "approx_eq", "value": v}
            elif isinstance(v, (str, bool)):
                promoted[k] = {"kind": "in_set", "values": [v]}
            else:
                promoted[k] = v  # let Pydantic validate/reject
        data["condition_on"] = promoted
        return data


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
    def validate_arms(self) -> AtomicSpec:
        labels = [a.label for a in self.arms]
        if len(labels) != len(set(labels)):
            raise ValueError("arm labels must be unique")

        # Difference/ratio require exactly 2 arms and explicit ref_arm
        if self.comparison.kind in (ComparisonKind.DIFFERENCE, ComparisonKind.RATIO):
            if len(self.arms) != 2:
                raise ValueError(
                    f"{self.comparison.kind} comparison requires exactly 2 arms, "
                    f"got {len(self.arms)}"
                )
            if not self.comparison.ref_arm:
                # Auto-fill ref_arm from second arm for backward compat.
                # Log warning so compiler issues are visible.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "AtomicSpec %s: ref_arm missing for %s comparison, "
                    "defaulting to '%s'. Fix the compiler prompt.",
                    self.spec_id, self.comparison.kind, labels[1],
                )
                object.__setattr__(
                    self.comparison, "ref_arm", labels[1]
                )
            elif self.comparison.ref_arm not in labels:
                raise ValueError(
                    f"ref_arm '{self.comparison.ref_arm}' not found in arm "
                    f"labels: {labels}"
                )
        return self

    @model_validator(mode="after")
    def validate_arm_measurement_compatibility(self) -> AtomicSpec:
        """Reject structurally incoherent arm/measurement combinations.

        Discovered via P06 forensics on policy_equity: the verifier executor
        for arm.kind=ADJUST returns 1-D samples of the OUTCOME variable only
        (E[Y | do(X=x)]) — there is no treatment column, no conditioning
        columns, no DataFrame at all. So measurements that need a multivariate
        context cannot be computed from those samples and previously fell
        through to a silent np.mean(samples) fallback in _measure_from_samples,
        producing wrong truth values.

        This validator enforces the contract at construction time so the
        compiler must either re-emit a coherent spec or abstain.

        NOTE: DISTRIBUTION is intentionally NOT included here. Its semantics
        under the current executor are placeholder/incomplete; rejecting it
        without confirmation could break otherwise-working specs. Reopen if
        evidence shows DISTRIBUTION + ADJUST is also incoherent.
        """
        incompatible_with_adjust = {
            MeasurementKind.CORRELATION,
            MeasurementKind.PARTIAL_CORRELATION,
        }
        if self.measurement.kind in incompatible_with_adjust:
            for arm in self.arms:
                if arm.kind == QueryKind.ADJUST:
                    raise ValueError(
                        f"AtomicSpec {self.spec_id}: arm '{arm.label}' has "
                        f"kind=ADJUST but measurement.kind="
                        f"{self.measurement.kind.value}, which requires a "
                        f"multivariate DataFrame. ADJUST returns 1-D outcome "
                        f"samples only and cannot support correlation-style "
                        f"measurements. Use kind=BASELINE for observational "
                        f"correlation, or pick a measurement compatible with "
                        f"ADJUST samples (mean, variance, quantile, "
                        f"tail_prob, identifiability_check)."
                    )
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

    claims: list[ClaimCard] = Field(min_length=1, max_length=15)

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


class EpisodeTrace(BaseModel):
    """Structured trace of a solver's investigation during an OI episode."""

    accesses: list[ArtifactAccess] = Field(default_factory=list)
    claim_steps: dict[str, int] = Field(
        default_factory=dict,
        description="claim_id -> step when claim was submitted",
    )

    def accessed_artifact_ids(self) -> set[str]:
        """All artifact IDs the solver accessed."""
        return {a.artifact_id for a in self.accesses}
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
# Robust loader for frozen SubQuestionIntentV2 artifacts (P06 Experiment R)
# ---------------------------------------------------------------------------


class DroppedSpecRecord(BaseModel):
    """One verification_spec that was dropped during robust loading.

    Used to surface, in the experiment output, exactly which specs were
    invalid and why — instead of hard-failing the whole batch.
    """

    sq_id: str
    spec_id: str | None = None
    role: str = "required"  # "required" or "support"
    reason: str


class RobustLoadResult(BaseModel):
    """Outcome of loading frozen SubQuestionIntentV2 list with spec-level fallback.

    `loaded` is the list to feed to the runner. `abstained_sq_ids` are SQs
    whose every `required` spec was dropped — per the p06 forensics
    policy, the whole SQ is abstained and `support` specs are NOT promoted
    to required. `dropped_specs` is a per-spec audit trail.
    """

    loaded: list[SubQuestionIntentV2] = Field(default_factory=list)
    abstained_sq_ids: list[str] = Field(default_factory=list)
    dropped_specs: list[DroppedSpecRecord] = Field(default_factory=list)


def load_sub_questions_v2_robust(
    raw_sqs: list[dict[str, Any]],
) -> RobustLoadResult:
    """Load `SubQuestionIntentV2` list from raw frozen JSON, gracefully.

    Centralizes the JSON-to-pydantic step that was previously inlined in
    `scripts/p06_paired_run.py` and `scripts/rescore.py` (the only two
    historical-artifact loaders in the repo). Used by both — do not
    re-inline this logic anywhere.

    For each raw SQ:

    1. Each `verification_spec` raw dict is validated **individually**.
       Failing specs are dropped with the pydantic error captured in
       `dropped_specs`. This catches `adjust + partial_correlation`-style
       contract violations introduced upstream by an old compiler.
    2. If at least one `required` spec survives, the SQ is rebuilt from
       the survivors and appended to `loaded`.
    3. If **every** `required` spec falls, the SQ as a whole is abstained:
       its `sq_id` is added to `abstained_sq_ids` and it does NOT appear
       in `loaded`. Surviving `support` specs are dropped on the floor —
       the policy is "core gone => SQ unaddressed", we do not synthesize
       cosmetic coverage by promoting supports. (Decision recorded in
       research/notes/p06_phase_c_forensics.md, "Required-fallback
       policy".)
    4. If the outer `SubQuestionIntentV2` construction itself fails after
       successful spec filtering (e.g. malformed `text_gloss`), the SQ is
       abstained and the failure is recorded as a synthetic dropped spec
       with `spec_id=None`.

    The function never raises on a per-spec or per-SQ failure. The only
    way it raises is on a malformed `raw_sqs` argument (wrong type).

    Args:
        raw_sqs: list of raw dicts loaded from `src.json["sub_questions_v2"]`.

    Returns:
        `RobustLoadResult` with `loaded`, `abstained_sq_ids`, `dropped_specs`.
    """
    from pydantic import ValidationError

    if not isinstance(raw_sqs, list):
        raise TypeError(
            f"load_sub_questions_v2_robust expects list[dict], got {type(raw_sqs).__name__}"
        )

    result = RobustLoadResult()

    for raw_sq in raw_sqs:
        if not isinstance(raw_sq, dict):
            continue
        sq_id = str(raw_sq.get("sq_id") or "<unknown>")
        raw_specs = raw_sq.get("verification_specs") or []

        surviving_specs: list[dict[str, Any]] = []
        for raw_spec in raw_specs:
            if not isinstance(raw_spec, dict):
                continue
            inner = raw_spec.get("spec") or {}
            spec_id = inner.get("spec_id") if isinstance(inner, dict) else None
            role = raw_spec.get("role", "required")
            try:
                VerificationSpec.model_validate(raw_spec)
            except ValidationError as e:
                result.dropped_specs.append(
                    DroppedSpecRecord(
                        sq_id=sq_id,
                        spec_id=spec_id,
                        role=role,
                        reason=str(e),
                    )
                )
                continue
            surviving_specs.append(raw_spec)

        # Required-fallback policy: if no required survived, abstain whole SQ.
        survivors_required = [
            s for s in surviving_specs if s.get("role", "required") == "required"
        ]
        if not survivors_required:
            result.abstained_sq_ids.append(sq_id)
            continue

        rebuilt_raw = dict(raw_sq)
        rebuilt_raw["verification_specs"] = surviving_specs
        try:
            sq = SubQuestionIntentV2.model_validate(rebuilt_raw)
        except ValidationError as e:
            # Outer SQ construction failed even after spec filtering
            # (malformed text_gloss, missing tier, etc.). Abstain the SQ.
            result.abstained_sq_ids.append(sq_id)
            result.dropped_specs.append(
                DroppedSpecRecord(
                    sq_id=sq_id,
                    spec_id=None,
                    role="sq_outer",
                    reason=str(e),
                )
            )
            continue

        result.loaded.append(sq)

    return result


# ---------------------------------------------------------------------------
# Scoring parameters
# ---------------------------------------------------------------------------

MAX_CLAIMS: int = 15


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "QueryKind",
    "ApproxEq",
    "ConditionRange",
    "QuantileRange",
    "InSet",
    "ConditionPredicate",
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
    "EpisodeTrace",
    "AtomVerdict",
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
    "DroppedSpecRecord",
    "RobustLoadResult",
    "load_sub_questions_v2_robust",
    "SubQuestionScore",
    "EpisodeSubQuestionScore",
    "MAX_CLAIMS",
]
