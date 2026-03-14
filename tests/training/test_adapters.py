"""Tests for the adapter layer between verifiers and SREG models."""

import pytest

from sreg.models.episode import ActionDef, ActionType
from sreg.training.adapters import (
    action_id_is_intervene,
    extract_answer,
    make_intervene_action,
    make_observe_action,
    make_submit_action,
    step_result_to_text,
)
from sreg.training.types import SubmitPayload


class TestMakeObserveAction:
    def test_creates_observe_action(self):
        action = make_observe_action("obs_water_temp")
        assert action.type == ActionType.OBSERVE
        assert action.action_id == "obs_water_temp"

    def test_node_is_none(self):
        action = make_observe_action("obs_x")
        assert action.node is None


class TestMakeInterveneAction:
    def test_creates_intervene_action(self):
        action = make_intervene_action("int_set_temp_high")
        assert action.type == ActionType.INTERVENE
        assert action.action_id == "int_set_temp_high"


class TestMakeSubmitAction:
    def test_distribution_submit(self):
        payload = SubmitPayload(distribution={"low": 0.3, "high": 0.7})
        action = make_submit_action(payload, "infer_target")
        assert action.type == ActionType.SUBMIT
        assert action.answer == {"low": 0.3, "high": 0.7}

    def test_choice_submit(self):
        payload = SubmitPayload(choice="hypothesis_A")
        action = make_submit_action(payload, "hypothesis_selection")
        assert action.type == ActionType.SUBMIT
        # Choice types get a dummy answer dict; real answer is in SubmitPayload
        assert action.answer == {"_submitted": 1.0}

    def test_adjustment_set_submit(self):
        payload = SubmitPayload(adjustment_set=["x", "y"])
        action = make_submit_action(payload, "adjustment_set")
        assert action.type == ActionType.SUBMIT


class TestExtractAnswer:
    def test_distribution(self):
        p = SubmitPayload(distribution={"a": 0.5, "b": 0.5})
        assert extract_answer(p, "infer_target") == {"a": 0.5, "b": 0.5}

    def test_choice(self):
        p = SubmitPayload(choice="yes")
        assert extract_answer(p, "should_condition") == "yes"

    def test_set(self):
        p = SubmitPayload(adjustment_set=["x"])
        assert extract_answer(p, "adjustment_set") == ["x"]

    def test_wrong_field_raises(self):
        p = SubmitPayload(choice="A")
        with pytest.raises(ValueError):
            extract_answer(p, "infer_target")

    def test_unknown_type_raises(self):
        p = SubmitPayload(choice="A")
        with pytest.raises(ValueError, match="Unknown eval type"):
            extract_answer(p, "fake_type")


class TestStepResultToText:
    def test_observation_text(self):
        from sreg.models.episode import Action, ActionType, Observation, StepResult

        result = StepResult(
            step=0,
            action=Action(type=ActionType.OBSERVE, action_id="obs_x"),
            observation=Observation(
                node="temperature",
                state="high",
                description="temperature was observed to be HIGH",
            ),
            remaining_budget=4,
        )
        text = step_result_to_text(result)
        assert "temperature was observed to be HIGH" in text
        assert "Budget remaining: 4" in text

    def test_extra_observations(self):
        from sreg.models.episode import Action, ActionType, Observation, StepResult

        result = StepResult(
            step=0,
            action=Action(type=ActionType.OBSERVE, action_id="obs_group"),
            observation=Observation(node="a", state="low", description="a is LOW"),
            extra_observations=[
                Observation(node="b", state="high", description="b is HIGH"),
            ],
            remaining_budget=3,
        )
        text = step_result_to_text(result)
        assert "a is LOW" in text
        assert "b is HIGH" in text

    def test_submit_result(self):
        from sreg.models.episode import Action, ActionType, StepResult

        result = StepResult(
            step=2,
            action=Action(type=ActionType.SUBMIT, answer={"low": 0.5, "high": 0.5}),
            remaining_budget=2,
        )
        text = step_result_to_text(result)
        assert "Action processed" in text
        assert "Budget remaining: 2" in text

    def test_distribution_in_text(self):
        from sreg.models.episode import Action, ActionType, StepResult

        result = StepResult(
            step=1,
            action=Action(type=ActionType.QUERY_DISTRIBUTION, node="target"),
            distribution={"low": 0.4, "high": 0.6},
            remaining_budget=5,
        )
        text = step_result_to_text(result)
        assert "Distribution:" in text
        assert "0.4000" in text


class TestActionIdIsIntervene:
    def test_observe_action(self):
        defs = [ActionDef(id="obs_x", action_type="observe", nodes=["x"], cost=1)]
        assert action_id_is_intervene("obs_x", defs) is False

    def test_intervene_action(self):
        defs = [
            ActionDef(
                id="int_x_high",
                action_type="intervene",
                nodes=["x"],
                cost=2,
                effects={"x": "high"},
            )
        ]
        assert action_id_is_intervene("int_x_high", defs) is True

    def test_unknown_action_id(self):
        defs = [ActionDef(id="obs_x", action_type="observe", nodes=["x"], cost=1)]
        assert action_id_is_intervene("unknown", defs) is False
