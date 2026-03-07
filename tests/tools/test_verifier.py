"""Tests for VerifierTool."""

import pytest

from sreg.tools.verifier import VerifierTool


@pytest.fixture
def verifier():
    return VerifierTool()


def test_perfect_score(verifier):
    dist = {"low": 0.2, "medium": 0.3, "high": 0.5}
    score = verifier.score(
        agent_posterior=dist,
        true_posterior=dist,
        budget_used=3,
        budget_total=5,
    )
    assert score.functional_score < 1e-6  # KL(P||P) ≈ 0


def test_bad_score(verifier):
    agent = {"low": 0.9, "medium": 0.05, "high": 0.05}
    true = {"low": 0.1, "medium": 0.1, "high": 0.8}
    score = verifier.score(
        agent_posterior=agent,
        true_posterior=true,
        budget_used=2,
        budget_total=5,
    )
    assert score.functional_score > 0.5  # Very different distributions


def test_kl_divergence_symmetric_check(verifier):
    p = {"a": 0.7, "b": 0.3}
    q = {"a": 0.3, "b": 0.7}
    kl_pq = verifier.kl_divergence(p, q)
    kl_qp = verifier.kl_divergence(q, p)
    # KL is not symmetric in general
    assert kl_pq > 0
    assert kl_qp > 0


def test_kl_divergence_non_negative(verifier):
    p = {"a": 0.6, "b": 0.4}
    q = {"a": 0.5, "b": 0.5}
    assert verifier.kl_divergence(p, q) >= 0


def test_information_efficiency(verifier):
    score = verifier.score(
        agent_posterior={"a": 0.5, "b": 0.5},
        true_posterior={"a": 0.5, "b": 0.5},
        budget_used=3,
        budget_total=5,
        max_info_gain=1.0,
        achieved_info_gain=0.7,
    )
    assert abs(score.information_efficiency - 0.7) < 1e-6


def test_per_step_scoring(verifier):
    per_step_data = [
        {
            "step": 0,
            "agent_posterior": {"a": 0.5, "b": 0.5},
            "true_posterior": {"a": 0.6, "b": 0.4},
            "cumulative_info_gain": 0.1,
            "entropy": 0.97,
        },
        {
            "step": 1,
            "agent_posterior": {"a": 0.7, "b": 0.3},
            "true_posterior": {"a": 0.8, "b": 0.2},
            "cumulative_info_gain": 0.3,
            "entropy": 0.72,
        },
    ]
    score = verifier.score(
        agent_posterior={"a": 0.7, "b": 0.3},
        true_posterior={"a": 0.8, "b": 0.2},
        per_step_data=per_step_data,
        budget_used=2,
        budget_total=5,
    )
    assert len(score.per_step) == 2
    assert score.per_step[0].step == 0
    assert score.per_step[1].step == 1
    assert all(s.posterior_kl >= 0 for s in score.per_step)


def test_budget_tracking(verifier):
    score = verifier.score(
        agent_posterior={"a": 0.5, "b": 0.5},
        true_posterior={"a": 0.5, "b": 0.5},
        budget_used=3,
        budget_total=5,
    )
    assert score.budget_used == 3
    assert score.budget_total == 5
