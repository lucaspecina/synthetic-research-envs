"""Tests for teacher output model."""

from sreg.models.episode import Action, ActionType
from sreg.models.teacher import TeacherOutput


def test_teacher_output_with_recommendation():
    output = TeacherOutput(
        posterior={"slow": 0.2, "medium": 0.3, "fast": 0.5},
        recommended_action=Action(type=ActionType.OBSERVE, node="thermal_flux"),
        information_gain=0.45,
        entropy=1.2,
    )
    assert output.recommended_action is not None
    assert output.information_gain == 0.45
    assert sum(output.posterior.values()) == 1.0


def test_teacher_output_terminal():
    output = TeacherOutput(
        posterior={"slow": 0.05, "medium": 0.15, "fast": 0.80},
        recommended_action=None,
        information_gain=0.0,
        entropy=0.7,
    )
    assert output.recommended_action is None
    assert output.information_gain == 0.0


def test_teacher_output_serialization_roundtrip():
    output = TeacherOutput(
        posterior={"a": 0.4, "b": 0.6},
        recommended_action=Action(type=ActionType.OBSERVE, node="x"),
        information_gain=0.3,
        entropy=0.97,
    )
    json_str = output.model_dump_json()
    restored = TeacherOutput.model_validate_json(json_str)
    assert restored.posterior == output.posterior
    assert restored.recommended_action.node == "x"
