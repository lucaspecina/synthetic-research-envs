"""Tests for submit payload validation."""

import pytest

from sreg.training.types import SubmitPayload
from sreg.training.validators import validate_submit_payload


class TestValidateSubmitPayload:
    """Test payload validation by eval type."""

    # --- Distribution types ---

    def test_infer_target_valid(self):
        p = SubmitPayload(distribution={"low": 0.3, "high": 0.7})
        validate_submit_payload(p, "infer_target")  # no error

    def test_causal_effect_valid(self):
        p = SubmitPayload(distribution={"low": 0.5, "high": 0.5})
        validate_submit_payload(p, "causal_effect")

    def test_infer_latent_cause_valid(self):
        p = SubmitPayload(distribution={"active": 0.8, "inactive": 0.2})
        validate_submit_payload(p, "infer_latent_cause")

    def test_distribution_type_rejects_choice(self):
        p = SubmitPayload(choice="hypothesis_A")
        with pytest.raises(ValueError, match="requires a 'distribution'"):
            validate_submit_payload(p, "infer_target")

    def test_distribution_type_rejects_set(self):
        p = SubmitPayload(adjustment_set=["x"])
        with pytest.raises(ValueError, match="requires a 'distribution'"):
            validate_submit_payload(p, "causal_effect")

    # --- Choice types ---

    def test_hypothesis_selection_valid(self):
        p = SubmitPayload(choice="hypothesis_A")
        validate_submit_payload(p, "hypothesis_selection")

    def test_nbo_valid(self):
        p = SubmitPayload(choice="temperature")
        validate_submit_payload(p, "next_best_observation")

    def test_best_intervention_valid(self):
        p = SubmitPayload(choice="water_temp:high")
        validate_submit_payload(p, "best_intervention")

    def test_compare_interventions_valid(self):
        p = SubmitPayload(choice="A")
        validate_submit_payload(p, "compare_interventions")

    def test_should_condition_valid(self):
        p = SubmitPayload(choice="yes")
        validate_submit_payload(p, "should_condition")

    def test_choice_type_rejects_distribution(self):
        p = SubmitPayload(distribution={"a": 0.5, "b": 0.5})
        with pytest.raises(ValueError, match="requires a 'choice'"):
            validate_submit_payload(p, "hypothesis_selection")

    # --- Set types ---

    def test_adjustment_set_valid(self):
        p = SubmitPayload(adjustment_set=["x", "y"])
        validate_submit_payload(p, "adjustment_set")

    def test_adjustment_set_empty_list(self):
        p = SubmitPayload(adjustment_set=[])
        validate_submit_payload(p, "adjustment_set")  # empty set is valid

    def test_set_type_rejects_choice(self):
        p = SubmitPayload(choice="x")
        with pytest.raises(ValueError, match="requires an 'adjustment_set'"):
            validate_submit_payload(p, "adjustment_set")

    # --- General validation ---

    def test_empty_payload_rejected(self):
        p = SubmitPayload()
        with pytest.raises(ValueError, match="empty"):
            validate_submit_payload(p, "infer_target")

    def test_multiple_fields_rejected(self):
        p = SubmitPayload(choice="A", distribution={"a": 1.0})
        with pytest.raises(ValueError, match="multiple fields"):
            validate_submit_payload(p, "infer_target")

    def test_unknown_eval_type(self):
        p = SubmitPayload(choice="x")
        with pytest.raises(ValueError, match="Unknown eval type"):
            validate_submit_payload(p, "nonexistent_type")

    # --- Distribution sanity checks ---

    def test_distribution_negative_values(self):
        p = SubmitPayload(distribution={"a": -0.5, "b": 1.5})
        with pytest.raises(ValueError, match="negative"):
            validate_submit_payload(p, "infer_target")

    def test_distribution_bad_sum(self):
        p = SubmitPayload(distribution={"a": 0.1, "b": 0.1})
        with pytest.raises(ValueError, match="sums to"):
            validate_submit_payload(p, "infer_target")

    def test_distribution_empty(self):
        p = SubmitPayload(distribution={})
        with pytest.raises(ValueError, match="empty"):
            validate_submit_payload(p, "infer_target")
