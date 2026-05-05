"""Validadores de pesos discretos.

`GoldQuestion.weight ∈ {0.08, 0.12, 0.16, 0.20}` y
`Criterion.weight ∈ {1, 2, 3}` son pesos discretos anti-ajuste-fino
(ver `ARCHITECTURE.md` §6).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sreg.v1_5.contracts import (
    ALLOWED_CRITERION_WEIGHTS,
    ALLOWED_GQ_WEIGHTS,
    AnswerKey,
    AnswerKeyAnchor,
    Criterion,
    EvidenceArtifact,
    GoldQuestion,
    PaperInsights,
    PaperNarrativeCapsule,
    QuestionsBundle,
    Rubric,
    ValidatedPhenomenon,
    ValidationIssue,
    ValidationReport,
    ValidatorVote,
    WorldMetadata,
    WorldSpec,
)


def _make_anchor() -> AnswerKeyAnchor:
    return AnswerKeyAnchor(path="x", match="approx", tolerance=0.1)


def _make_criterion(weight: int = 2) -> Criterion:
    return Criterion(
        text="t",
        weight=weight,
        role="core",
        anchor=_make_anchor(),
        scoring_hint="h",
    )


def _make_evidence() -> EvidenceArtifact:
    return EvidenceArtifact(script="pass", numerical_result={})


def _make_gq(weight: float = 0.20) -> GoldQuestion:
    return GoldQuestion(
        id="GQ",
        text="t",
        weight=weight,
        role="required",
        answer_key=AnswerKey(summary="s", numeric={}),
        answer_key_provenance=[_make_evidence()],
        identification_hint="h",
        rubric=Rubric(criteria=[_make_criterion()]),
    )


# ---------------------------------------------------------------------------
# Criterion.weight
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("weight", list(ALLOWED_CRITERION_WEIGHTS))
def test_criterion_accepts_allowed_weights(weight: int) -> None:
    c = _make_criterion(weight=weight)
    assert c.weight == weight


@pytest.mark.parametrize("weight", [0, 4, 5, 10, -1])
def test_criterion_rejects_invalid_weights(weight: int) -> None:
    with pytest.raises(ValidationError):
        _make_criterion(weight=weight)


# ---------------------------------------------------------------------------
# GoldQuestion.weight
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("weight", list(ALLOWED_GQ_WEIGHTS))
def test_gq_accepts_allowed_weights(weight: float) -> None:
    gq = _make_gq(weight=weight)
    assert gq.weight == weight


@pytest.mark.parametrize("weight", [0.0, 0.05, 0.10, 0.25, 0.30, 1.0, -0.1])
def test_gq_rejects_invalid_weights(weight: float) -> None:
    with pytest.raises(ValidationError):
        _make_gq(weight=weight)


# ---------------------------------------------------------------------------
# WorldSpec.observation_noise — validator cruzado con formalism
# ---------------------------------------------------------------------------


def _make_world(formalism="scm", observation_noise=None) -> WorldSpec:
    return WorldSpec(
        formalism=formalism,
        variables=[],
        relationships=[],
        parameters={},
        metadata=WorldMetadata(domain="generic"),
        observation_noise=observation_noise,
    )


def test_world_scm_without_noise_ok() -> None:
    w = _make_world(formalism="scm", observation_noise=None)
    assert w.observation_noise is None


def test_world_ode_without_noise_ok() -> None:
    w = _make_world(formalism="ode", observation_noise=None)
    assert w.observation_noise is None


def test_world_ode_with_zero_noise_ok() -> None:
    w = _make_world(formalism="ode", observation_noise=0.0)
    assert w.observation_noise == 0.0


def test_world_ode_with_positive_noise_ok() -> None:
    w = _make_world(formalism="ode", observation_noise=0.5)
    assert w.observation_noise == 0.5


def test_world_scm_with_noise_fails() -> None:
    with pytest.raises(ValidationError):
        _make_world(formalism="scm", observation_noise=0.1)


def test_world_ode_with_negative_noise_fails() -> None:
    with pytest.raises(ValidationError):
        _make_world(formalism="ode", observation_noise=-0.1)


# ---------------------------------------------------------------------------
# AnswerKeyAnchor — validator cruzado por modo de match
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"path": "x", "match": "approx", "tolerance": 0.1},
        {"path": "x", "match": "approx", "tolerance": 0.0},
        {"path": "x", "match": "equals", "value": 0.5},
        {"path": "x", "match": "equals", "value": "categoria_a"},
        {"path": "x", "match": "enum", "value": ["a", "b"]},
        {"path": "x", "match": "mentioned"},
    ],
)
def test_anchor_valid_combinations(kwargs: dict) -> None:
    a = AnswerKeyAnchor(**kwargs)
    assert a.match == kwargs["match"]


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"path": "x", "match": "approx"}, "approx sin tolerance"),
        ({"path": "x", "match": "approx", "tolerance": 0.1, "value": 1}, "approx con value"),
        ({"path": "x", "match": "approx", "tolerance": -0.1}, "approx con tolerance negativa"),
        ({"path": "x", "match": "equals"}, "equals sin value"),
        ({"path": "x", "match": "equals", "value": 1, "tolerance": 0.1}, "equals con tolerance"),
        ({"path": "x", "match": "enum"}, "enum sin value"),
        ({"path": "x", "match": "enum", "value": [1], "tolerance": 0.1}, "enum con tolerance"),
        ({"path": "x", "match": "mentioned", "tolerance": 0.1}, "mentioned con tolerance"),
        ({"path": "x", "match": "mentioned", "value": 1}, "mentioned con value"),
    ],
)
def test_anchor_invalid_combinations(kwargs: dict, reason: str) -> None:
    with pytest.raises(ValidationError):
        AnswerKeyAnchor(**kwargs)


# ---------------------------------------------------------------------------
# Rubric / QuestionsBundle — listas no pueden estar vacías
# y Rubric debe tener al menos un Criterion core.
# ---------------------------------------------------------------------------


def test_rubric_empty_criteria_fails() -> None:
    with pytest.raises(ValidationError):
        Rubric(criteria=[])


def test_questions_bundle_empty_fails() -> None:
    with pytest.raises(ValidationError):
        QuestionsBundle(questions=[])


def test_rubric_only_core_ok() -> None:
    r = Rubric(criteria=[_make_criterion(weight=2)])
    assert r.criteria[0].role == "core"


def test_rubric_core_plus_bonus_ok() -> None:
    core = _make_criterion(weight=2)
    bonus = Criterion(
        text="bonus por incertidumbre",
        weight=1,
        role="bonus",
        anchor=AnswerKeyAnchor(path="ci", match="mentioned"),
        scoring_hint="acreditar si menciona CI",
    )
    r = Rubric(criteria=[core, bonus])
    assert {c.role for c in r.criteria} == {"core", "bonus"}


def test_rubric_only_bonus_fails() -> None:
    """Una rubric con solo criterios bonus no es evaluable: necesita al menos 1 core."""
    bonus = Criterion(
        text="bonus por incertidumbre",
        weight=1,
        role="bonus",
        anchor=AnswerKeyAnchor(path="ci", match="mentioned"),
        scoring_hint="acreditar si menciona CI",
    )
    with pytest.raises(ValidationError):
        Rubric(criteria=[bonus])


# ---------------------------------------------------------------------------
# ValidationReport — target_to_reiterate consistency con passed
# ---------------------------------------------------------------------------


def test_validation_passed_without_target_ok() -> None:
    r = ValidationReport(passed=True)
    assert r.target_to_reiterate is None


def test_validation_failed_with_target_ok() -> None:
    r = ValidationReport(
        passed=False,
        target_to_reiterate="world",
        issues=[ValidationIssue(artifact="world", severity="error", description="x")],
    )
    assert r.target_to_reiterate == "world"


def test_validation_failed_without_issues_or_artifacts_fails() -> None:
    """passed=False sin `issues` ni `invalidated_artifacts` no es accionable."""
    with pytest.raises(ValidationError):
        ValidationReport(passed=False, target_to_reiterate="world")


def test_validation_passed_with_target_fails() -> None:
    """Si pasa, no debería declarar a qué etapa rehacer."""
    with pytest.raises(ValidationError):
        ValidationReport(passed=True, target_to_reiterate="world")


def test_validation_failed_without_target_fails() -> None:
    """Si no pasa, debe declarar a qué etapa rehacer."""
    with pytest.raises(ValidationError):
        ValidationReport(passed=False)


# ---------------------------------------------------------------------------
# GoldQuestion — answer_key_provenance no puede estar vacío
# ---------------------------------------------------------------------------


def test_gq_empty_provenance_fails() -> None:
    """Una GQ sin scripts ejecutables que respalden su AnswerKey no es válida."""
    with pytest.raises(ValidationError):
        GoldQuestion(
            id="GQ",
            text="t",
            weight=0.20,
            role="required",
            answer_key=AnswerKey(summary="s", numeric={}),
            answer_key_provenance=[],
            identification_hint="h",
            rubric=Rubric(criteria=[_make_criterion()]),
        )


# ---------------------------------------------------------------------------
# ValidatorVote — failure_reason consistency
# ---------------------------------------------------------------------------


def _make_vote(
    *,
    vote: str = "passes",
    failure_reason: str | None = None,
    iteration: int = 1,
) -> ValidatorVote:
    return ValidatorVote(
        validator_id="v1",
        target_intended_id="ip1",
        iteration=iteration,
        vote=vote,  # type: ignore[arg-type]
        margin=0.8,
        fragility=0.2,
        evidence=[_make_evidence()],
        failure_reason=failure_reason,
    )


def test_validator_vote_passes_without_failure_reason_ok() -> None:
    v = _make_vote(vote="passes")
    assert v.failure_reason is None


def test_validator_vote_weak_pass_requires_failure_reason() -> None:
    """`weak_pass` no graduates silenciosamente — exige `failure_reason`."""
    with pytest.raises(ValidationError):
        _make_vote(vote="weak_pass", failure_reason=None)


def test_validator_vote_fails_requires_failure_reason() -> None:
    with pytest.raises(ValidationError):
        _make_vote(vote="fails", failure_reason=None)


def test_validator_vote_fails_with_reason_ok() -> None:
    v = _make_vote(vote="fails", failure_reason="coef de U débil; collider no se materializa")
    assert v.vote == "fails"


def test_validator_vote_negative_iteration_fails() -> None:
    with pytest.raises(ValidationError):
        _make_vote(iteration=-1)


def test_validator_vote_empty_evidence_fails() -> None:
    with pytest.raises(ValidationError):
        ValidatorVote(
            validator_id="v1",
            target_intended_id="ip1",
            iteration=0,
            vote="passes",
            margin=0.5,
            fragility=0.1,
            evidence=[],
        )


def test_validator_vote_passes_with_failure_reason_fails() -> None:
    """vote='passes' con failure_reason es contradictorio."""
    with pytest.raises(ValidationError):
        _make_vote(vote="passes", failure_reason="esto no debería estar")


def test_validator_vote_iteration_zero_with_delta_fails() -> None:
    """iteration=0 con delta_from_previous no nulo: no hay previa."""
    with pytest.raises(ValidationError):
        ValidatorVote(
            validator_id="v1",
            target_intended_id="ip1",
            iteration=0,
            vote="passes",
            margin=0.5,
            fragility=0.1,
            evidence=[_make_evidence()],
            delta_from_previous={"x": 1},
        )


@pytest.mark.parametrize("margin", [-0.1, 1.5, 100.0])
def test_validator_vote_margin_out_of_range_fails(margin: float) -> None:
    with pytest.raises(ValidationError):
        ValidatorVote(
            validator_id="v1",
            target_intended_id="ip1",
            iteration=0,
            vote="passes",
            margin=margin,
            fragility=0.1,
            evidence=[_make_evidence()],
        )


@pytest.mark.parametrize("fragility", [-0.1, 1.5])
def test_validator_vote_fragility_out_of_range_fails(fragility: float) -> None:
    with pytest.raises(ValidationError):
        ValidatorVote(
            validator_id="v1",
            target_intended_id="ip1",
            iteration=0,
            vote="passes",
            margin=0.5,
            fragility=fragility,
            evidence=[_make_evidence()],
        )


# ---------------------------------------------------------------------------
# ValidatedPhenomenon — only-passes consistency + source_intended_id match
# ---------------------------------------------------------------------------


def _vp_kwargs(**overrides) -> dict:
    base = dict(
        id="vp1",
        source_intended_id="ip1",
        kind="collider",
        description="LBW collider entre Smoking y U",
        relevant_variables=["smoking", "lbw", "u"],
        validator_votes=[_make_vote(vote="passes")],
        margin=0.8,
        fragility=0.2,
        evidence=[_make_evidence()],
    )
    base.update(overrides)
    return base


def test_validated_phenomenon_with_passes_vote_ok() -> None:
    vp = ValidatedPhenomenon(**_vp_kwargs())
    assert vp.validator_votes[0].vote == "passes"


def test_validated_phenomenon_rejects_weak_pass_vote() -> None:
    """`weak_pass` NO graduates a ValidatedPhenomenon."""
    weak = _make_vote(vote="weak_pass", failure_reason="margin marginal")
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(**_vp_kwargs(validator_votes=[weak]))


def test_validated_phenomenon_rejects_fails_vote() -> None:
    fails = _make_vote(vote="fails", failure_reason="no materializa")
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(**_vp_kwargs(validator_votes=[fails]))


def test_validated_phenomenon_empty_votes_fails() -> None:
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(**_vp_kwargs(validator_votes=[]))


def test_validated_phenomenon_target_mismatch_fails() -> None:
    """`source_intended_id` debe coincidir con cada `target_intended_id` de los votes."""
    mismatched = _make_vote(vote="passes")
    # `mismatched.target_intended_id` es "ip1"; usamos otro source para forzar mismatch
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(
            **_vp_kwargs(source_intended_id="ip_OTRO", validator_votes=[mismatched])
        )


def test_validated_phenomenon_empty_evidence_fails() -> None:
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(**_vp_kwargs(evidence=[]))


def test_validated_phenomenon_orphan_evidence_fails() -> None:
    """Evidence con script que no aparece en ningún vote es huérfana."""
    orphan = EvidenceArtifact(script="pass # script huérfano", numerical_result={})
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(**_vp_kwargs(evidence=[orphan]))


def test_validated_phenomenon_tampered_numerical_result_fails() -> None:
    """Evidence con MISMO script pero numerical_result distinto es huérfana.

    Detecta caso "Architect copia código pero retoca el número": el
    fingerprint compara `(script, numerical_result)`, no solo script.
    """
    # vote_evidence (en _make_evidence): numerical_result={}
    tampered = EvidenceArtifact(script="pass", numerical_result={"ate": 999.0})
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(**_vp_kwargs(evidence=[tampered]))


def test_validated_phenomenon_margin_above_min_vote_fails() -> None:
    """Margin agregado debe ser <= min(votes.margin) (conservador)."""
    vote = _make_vote(vote="passes")  # margin=0.8
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(
            **_vp_kwargs(validator_votes=[vote], margin=0.95)  # > 0.8 → fails
        )


def test_validated_phenomenon_fragility_below_max_vote_fails() -> None:
    """Fragility agregada debe ser >= max(votes.fragility)."""
    vote = _make_vote(vote="passes")  # fragility=0.2
    with pytest.raises(ValidationError):
        ValidatedPhenomenon(
            **_vp_kwargs(validator_votes=[vote], fragility=0.05)  # < 0.2 → fails
        )


# ---------------------------------------------------------------------------
# PaperInsights — narrative_capsule obligatorio (anti-leak)
# ---------------------------------------------------------------------------


def test_paper_insights_without_narrative_capsule_fails() -> None:
    """`narrative_capsule` es obligatorio post-Ronda 13 (anti-leak)."""
    with pytest.raises(ValidationError):
        PaperInsights(
            paper_id="p1",
            objective="x",
            entities=[],
            mechanisms=[],
            phenomena=[],
            complications=[],
            counterintuitive_priors=[],
            realism_bounds=[],
            # falta narrative_capsule
        )


def test_paper_insights_with_capsule_ok() -> None:
    p = PaperInsights(
        paper_id="p1",
        objective="x",
        entities=[],
        mechanisms=[],
        phenomena=[],
        complications=[],
        counterintuitive_priors=[],
        realism_bounds=[],
        narrative_capsule=PaperNarrativeCapsule(
            domain="d", population="p"
        ),
    )
    assert p.narrative_capsule is not None
