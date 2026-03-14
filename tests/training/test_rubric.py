"""Tests for reward computation (rubric dispatch)."""

import pytest

from sreg.training.rubric import score_submission
from sreg.training.types import SubmitPayload


class TestScoreDistribution:
    """Test distribution-type eval scoring."""

    def test_perfect_answer(self):
        """Perfect match should give reward ~1.0."""
        payload = SubmitPayload(distribution={"low": 0.3, "high": 0.7})
        correct = {"low": 0.3, "high": 0.7}
        score = score_submission(payload, "infer_target", correct)
        assert score > 0.95

    def test_bad_answer(self):
        """Opposite distribution should give low reward."""
        payload = SubmitPayload(distribution={"low": 0.9, "high": 0.1})
        correct = {"low": 0.1, "high": 0.9}
        score = score_submission(payload, "infer_target", correct)
        assert score < 0.8

    def test_uniform_vs_peaked(self):
        """Uniform guess vs peaked truth should be middling."""
        payload = SubmitPayload(distribution={"low": 0.5, "high": 0.5})
        correct = {"low": 0.1, "high": 0.9}
        score = score_submission(payload, "infer_target", correct)
        assert 0.0 < score < 1.0

    def test_causal_effect_scoring(self):
        """causal_effect uses same distribution scoring."""
        payload = SubmitPayload(distribution={"low": 0.2, "high": 0.8})
        correct = {"low": 0.2, "high": 0.8}
        score = score_submission(payload, "causal_effect", correct)
        assert score > 0.95

    def test_infer_latent_cause_scoring(self):
        payload = SubmitPayload(distribution={"active": 0.9, "inactive": 0.1})
        correct = {"active": 0.9, "inactive": 0.1}
        score = score_submission(payload, "infer_latent_cause", correct)
        assert score > 0.95

    def test_none_distribution_returns_zero(self):
        """If distribution is None, score is 0."""
        from sreg.training.rubric import _score_distribution

        assert _score_distribution(SubmitPayload(), {"a": 1.0}) == 0.0


class TestScoreChoice:
    """Test choice-type eval scoring."""

    def test_hypothesis_correct(self):
        payload = SubmitPayload(choice="H1")
        # correct_answer is kl_scores: lower KL = better
        correct = {"H1": 0.01, "H2": 1.5, "H3": 2.0}
        score = score_submission(payload, "hypothesis_selection", correct)
        assert score == 1.0

    def test_hypothesis_wrong(self):
        payload = SubmitPayload(choice="H3")
        correct = {"H1": 0.01, "H2": 1.5, "H3": 2.0}
        score = score_submission(payload, "hypothesis_selection", correct)
        assert score == 0.0

    def test_nbo_optimal(self):
        payload = SubmitPayload(choice="temp")
        correct = {"temp": 0.8, "pressure": 0.3, "wind": 0.1}
        score = score_submission(payload, "next_best_observation", correct)
        assert score == 1.0

    def test_nbo_suboptimal(self):
        payload = SubmitPayload(choice="wind")
        correct = {"temp": 0.8, "pressure": 0.3, "wind": 0.1}
        score = score_submission(payload, "next_best_observation", correct)
        assert score == pytest.approx(0.125, abs=0.01)

    def test_compare_interventions_correct(self):
        payload = SubmitPayload(choice="A")
        correct = {"int_a": 0.8, "int_b": 0.3}
        score = score_submission(payload, "compare_interventions", correct)
        assert score == 1.0

    def test_compare_interventions_wrong(self):
        payload = SubmitPayload(choice="B")
        correct = {"int_a": 0.8, "int_b": 0.3}
        score = score_submission(payload, "compare_interventions", correct)
        assert score == 0.0

    def test_should_condition_yes(self):
        payload = SubmitPayload(choice="yes")
        correct = {"yes": 1.0}
        score = score_submission(payload, "should_condition", correct)
        assert score == 1.0

    def test_should_condition_no(self):
        payload = SubmitPayload(choice="no")
        correct = {"no": 1.0}
        score = score_submission(payload, "should_condition", correct)
        assert score == 1.0

    def test_should_condition_wrong(self):
        payload = SubmitPayload(choice="yes")
        correct = {"no": 1.0}
        score = score_submission(payload, "should_condition", correct)
        assert score == 0.0

    def test_best_intervention(self):
        payload = SubmitPayload(choice="temp:high")
        correct = {"temp:high": 0.9, "temp:low": 0.2, "pressure:high": 0.5}
        score = score_submission(payload, "best_intervention", correct)
        assert score == 1.0


class TestScoreSet:
    """Test set-type eval scoring."""

    def test_adjustment_set_valid(self):
        payload = SubmitPayload(adjustment_set=["x", "y"])
        # valid_sets keys are sorted comma-joined
        correct = {"x,y": 1.0, "z": 1.0}
        score = score_submission(payload, "adjustment_set", correct)
        assert score == 1.0

    def test_adjustment_set_invalid(self):
        payload = SubmitPayload(adjustment_set=["a", "b"])
        correct = {"x,y": 1.0}
        score = score_submission(payload, "adjustment_set", correct)
        assert score == 0.0

    def test_empty_adjustment_set(self):
        payload = SubmitPayload(adjustment_set=[])
        correct = {"_empty_": 1.0, "x": 1.0}
        score = score_submission(payload, "adjustment_set", correct)
        assert score == 1.0


class TestEdgeCases:
    def test_unknown_eval_type(self):
        payload = SubmitPayload(choice="x")
        with pytest.raises(ValueError, match="Unknown eval type"):
            score_submission(payload, "nonexistent", {})

    def test_wrong_payload_type(self):
        """Distribution eval type but choice payload."""
        payload = SubmitPayload(choice="x")
        score = score_submission(payload, "infer_target", {"a": 0.5, "b": 0.5})
        # _score_distribution returns 0 when distribution is None
        assert score == 0.0

    def test_nan_in_distribution(self):
        """NaN values in distribution should be filtered, not crash."""
        payload = SubmitPayload(distribution={"a": float("nan"), "b": 0.5})
        correct = {"a": 0.5, "b": 0.5}
        # Should not raise, returns some score (filtered dist has only b)
        score = score_submission(payload, "infer_target", correct)
        assert isinstance(score, float)

    def test_inf_in_distribution(self):
        """Inf values in distribution should be filtered."""
        payload = SubmitPayload(distribution={"a": float("inf"), "b": 0.5})
        correct = {"a": 0.5, "b": 0.5}
        score = score_submission(payload, "infer_target", correct)
        assert isinstance(score, float)

    def test_custom_kl_cutoff(self):
        """KL cutoff should be configurable."""
        payload = SubmitPayload(distribution={"a": 0.9, "b": 0.1})
        correct = {"a": 0.1, "b": 0.9}
        score_default = score_submission(payload, "infer_target", correct)
        score_tight = score_submission(payload, "infer_target", correct, kl_cutoff=1.0)
        # Tighter cutoff should give lower reward for the same KL
        assert score_tight <= score_default

    def test_duplicate_adjustment_set_items(self):
        """Duplicate items in adjustment set."""
        payload = SubmitPayload(adjustment_set=["x", "x", "y"])
        # Sorted unique: "x,y" — but our scorer uses sorted(agent_set)
        # which preserves duplicates: "x,x,y" != "x,y"
        correct = {"x,y": 1.0}
        score = score_submission(payload, "adjustment_set", correct)
        # With duplicates, key becomes "x,x,y" which won't match "x,y"
        assert score == 0.0

    def test_choice_whitespace(self):
        """Choice with whitespace should be stripped."""
        payload = SubmitPayload(choice="  yes  ")
        correct = {"yes": 1.0}
        score = score_submission(payload, "should_condition", correct)
        assert score == 1.0
