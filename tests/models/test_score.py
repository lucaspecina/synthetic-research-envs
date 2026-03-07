"""Tests for scoring models."""

import pytest
from pydantic import ValidationError

from sreg.models.score import Score, StepScore


def test_step_score():
    ss = StepScore(
        step=0,
        posterior_kl=1.5,
        cumulative_info_gain=0.3,
        entropy=1.8,
    )
    assert ss.step == 0
    assert ss.posterior_kl == 1.5


def test_score_complete():
    score = Score(
        functional_score=0.15,
        information_efficiency=0.72,
        per_step=[
            StepScore(step=0, posterior_kl=2.0, cumulative_info_gain=0.0, entropy=2.0),
            StepScore(step=1, posterior_kl=1.0, cumulative_info_gain=0.5, entropy=1.5),
            StepScore(step=2, posterior_kl=0.15, cumulative_info_gain=1.2, entropy=0.8),
        ],
        budget_used=3,
        budget_total=5,
    )
    assert score.functional_score == 0.15
    assert len(score.per_step) == 3
    assert score.structural_score is None


def test_score_with_structural():
    score = Score(
        functional_score=0.2,
        information_efficiency=0.5,
        structural_score=0.85,
        budget_used=2,
        budget_total=3,
    )
    assert score.structural_score == 0.85


def test_score_rejects_invalid_efficiency():
    with pytest.raises(ValidationError):
        Score(
            functional_score=0.1,
            information_efficiency=1.5,  # > 1.0
            budget_used=1,
            budget_total=3,
        )


def test_score_serialization_roundtrip():
    score = Score(
        functional_score=0.3,
        information_efficiency=0.6,
        per_step=[
            StepScore(step=0, posterior_kl=1.0, cumulative_info_gain=0.2, entropy=1.5),
        ],
        budget_used=1,
        budget_total=5,
    )
    json_str = score.model_dump_json()
    restored = Score.model_validate_json(json_str)
    assert restored.functional_score == score.functional_score
    assert len(restored.per_step) == 1
