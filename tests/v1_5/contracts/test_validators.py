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
    GoldQuestion,
    QuestionsBundle,
    Rubric,
    VerifierQuery,
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


def _make_gq(weight: float = 0.20) -> GoldQuestion:
    return GoldQuestion(
        id="GQ",
        text="t",
        weight=weight,
        role="required",
        verifier_query=VerifierQuery(query_kind="ate", args={}),
        answer_key=AnswerKey(summary="s", numeric={}),
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
