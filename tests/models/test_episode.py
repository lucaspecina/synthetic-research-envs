"""Tests for episode data models."""

import pytest
from pydantic import ValidationError

from sreg.models.episode import Action, ActionType, Episode, Observation, StepResult

# --- Action ---


def test_observe_action():
    action = Action(type=ActionType.OBSERVE, node="thermal_flux")
    assert action.type == ActionType.OBSERVE
    assert action.node == "thermal_flux"


def test_submit_action():
    action = Action(
        type=ActionType.SUBMIT,
        answer={"low": 0.2, "medium": 0.3, "high": 0.5},
        confidence=0.8,
    )
    assert action.type == ActionType.SUBMIT
    assert sum(action.answer.values()) == pytest.approx(1.0)


def test_query_distribution_action():
    action = Action(type=ActionType.QUERY_DISTRIBUTION, node="crystal_growth")
    assert action.type == ActionType.QUERY_DISTRIBUTION


def test_observe_requires_node():
    with pytest.raises(ValidationError, match="requires a 'node'"):
        Action(type=ActionType.OBSERVE)


def test_submit_requires_answer():
    with pytest.raises(ValidationError, match="requires an 'answer'"):
        Action(type=ActionType.SUBMIT)


def test_confidence_bounded():
    with pytest.raises(ValidationError):
        Action(
            type=ActionType.SUBMIT,
            answer={"a": 0.5, "b": 0.5},
            confidence=1.5,
        )


# --- Observation ---


def test_observation_creation():
    obs = Observation(
        node="thermal_flux",
        state="high",
        value=0.84,
        description="thermal_flux was observed to be HIGH (value: 0.84)",
    )
    assert obs.node == "thermal_flux"
    assert obs.state == "high"


# --- StepResult ---


def test_step_result_with_observation():
    step = StepResult(
        step=0,
        action=Action(type=ActionType.OBSERVE, node="thermal_flux"),
        observation=Observation(
            node="thermal_flux",
            state="high",
            value=0.84,
            description="thermal_flux was observed to be HIGH",
        ),
        remaining_budget=4,
    )
    assert step.step == 0
    assert step.observation is not None
    assert step.remaining_budget == 4


def test_step_result_submit_no_observation():
    step = StepResult(
        step=3,
        action=Action(
            type=ActionType.SUBMIT,
            answer={"low": 0.1, "high": 0.9},
        ),
        remaining_budget=2,
    )
    assert step.observation is None


# --- Episode ---


def test_episode_creation():
    episode = Episode(
        id="ep-001",
        world_id="world-001",
        budget=5,
        initial_evidence=[
            Observation(
                node="inhibitor",
                state="present",
                description="growth_inhibitor is present",
            ),
        ],
        available_nodes=["thermal_flux", "pressure", "radiation"],
        node_costs={"thermal_flux": 1, "pressure": 1, "radiation": 2},
    )
    assert episode.budget == 5
    assert len(episode.available_nodes) == 3
    assert len(episode.steps) == 0


def test_episode_requires_positive_budget():
    with pytest.raises(ValidationError):
        Episode(
            id="ep-bad",
            world_id="w",
            budget=0,
            available_nodes=["a"],
            node_costs={"a": 1},
        )


def test_episode_serialization_roundtrip():
    episode = Episode(
        id="ep-001",
        world_id="world-001",
        budget=3,
        available_nodes=["a", "b"],
        node_costs={"a": 1, "b": 1},
    )
    json_str = episode.model_dump_json()
    restored = Episode.model_validate_json(json_str)
    assert restored.id == episode.id
    assert restored.available_nodes == episode.available_nodes
