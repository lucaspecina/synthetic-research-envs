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
    QuestionProposal,
    QuestionsBundle,
    Rubric,
    ValidationReport,
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
    r = ValidationReport(passed=False, target_to_reiterate="world")
    assert r.target_to_reiterate == "world"


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
# QuestionProposal — status consistency
# ---------------------------------------------------------------------------


def test_proposal_verified_with_complete_fields_ok() -> None:
    p = QuestionProposal(
        proposal_id="p1",
        author_run_id="explorer_1",
        focus="ip_collider",
        status="verified",
        question_text="¿Cuál es el efecto?",
        rubric_draft=Rubric(criteria=[_make_criterion()]),
        answer_key=AnswerKey(summary="s", numeric={}),
        answer_key_provenance=[_make_evidence()],
    )
    assert p.status == "verified"


def test_proposal_verified_missing_fields_fails() -> None:
    """status='verified' sin question_text/rubric/answer_key/provenance falla."""
    with pytest.raises(ValidationError):
        QuestionProposal(
            proposal_id="p1",
            author_run_id="explorer_1",
            focus="ip_collider",
            status="verified",
            # Faltan: question_text, rubric_draft, answer_key, provenance
        )


def test_proposal_rejected_with_failure_reason_ok() -> None:
    p = QuestionProposal(
        proposal_id="p1",
        author_run_id="explorer_1",
        focus="ip_collider",
        status="rejected_unconfirmed",
        failure_reason="el collider en LBW no se materializa en este SCM",
    )
    assert p.status == "rejected_unconfirmed"
    assert p.question_text is None


def test_proposal_rejected_without_failure_reason_fails() -> None:
    """status='rejected_unconfirmed' sin `failure_reason` falla."""
    with pytest.raises(ValidationError):
        QuestionProposal(
            proposal_id="p1",
            author_run_id="explorer_1",
            focus="ip_collider",
            status="rejected_unconfirmed",
        )


def test_proposal_verified_with_failure_reason_fails() -> None:
    """status='verified' NO debe tener `failure_reason`."""
    with pytest.raises(ValidationError):
        QuestionProposal(
            proposal_id="p1",
            author_run_id="explorer_1",
            focus="ip_collider",
            status="verified",
            question_text="?",
            rubric_draft=Rubric(criteria=[_make_criterion()]),
            answer_key=AnswerKey(summary="s", numeric={}),
            answer_key_provenance=[_make_evidence()],
            failure_reason="esto no debería estar acá",
        )
