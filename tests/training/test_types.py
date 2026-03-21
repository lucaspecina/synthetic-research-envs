"""Tests for training types."""

from sreg.training.types import (
    CHOICE_EVAL_TYPES,
    DISTRIBUTION_EVAL_TYPES,
    NUMERIC_EVAL_TYPES,
    SET_EVAL_TYPES,
    SubmitPayload,
)


class TestSubmitPayload:
    def test_choice_only(self):
        p = SubmitPayload(choice="hypothesis_A")
        assert p.choice == "hypothesis_A"
        assert p.distribution is None
        assert p.adjustment_set is None

    def test_distribution_only(self):
        p = SubmitPayload(distribution={"low": 0.3, "high": 0.7})
        assert p.choice is None
        assert p.distribution == {"low": 0.3, "high": 0.7}

    def test_adjustment_set_only(self):
        p = SubmitPayload(adjustment_set=["x", "y"])
        assert p.adjustment_set == ["x", "y"]
        assert p.choice is None

    def test_empty_payload(self):
        p = SubmitPayload()
        assert p.choice is None
        assert p.distribution is None
        assert p.adjustment_set is None


class TestEvalTypeSets:
    def test_no_overlap(self):
        """Eval type sets must be mutually exclusive."""
        assert not (DISTRIBUTION_EVAL_TYPES & CHOICE_EVAL_TYPES)
        assert not (DISTRIBUTION_EVAL_TYPES & SET_EVAL_TYPES)
        assert not (CHOICE_EVAL_TYPES & SET_EVAL_TYPES)
        assert not (DISTRIBUTION_EVAL_TYPES & NUMERIC_EVAL_TYPES)
        assert not (CHOICE_EVAL_TYPES & NUMERIC_EVAL_TYPES)
        assert not (SET_EVAL_TYPES & NUMERIC_EVAL_TYPES)

    def test_all_twelve_covered(self):
        """All 12 eval types must be in exactly one set."""
        all_types = (
            DISTRIBUTION_EVAL_TYPES | CHOICE_EVAL_TYPES
            | SET_EVAL_TYPES | NUMERIC_EVAL_TYPES
        )
        assert len(all_types) == 12
