"""Tests for task data models."""

from sreg.models.task import Task, TaskSpec, TaskType


def test_task_types():
    assert TaskType.INFER_TARGET == "infer_target"
    assert TaskType.NEXT_BEST_OBSERVATION == "next_best_observation"


def test_task_spec():
    spec = TaskSpec(
        type=TaskType.INFER_TARGET,
        target_node="crystal_growth",
        max_budget=5,
        difficulty="medium",
    )
    assert spec.type == TaskType.INFER_TARGET
    assert spec.max_budget == 5


def test_task_creation():
    task = Task(
        id="task-001",
        type=TaskType.INFER_TARGET,
        world_id="world-001",
        question="What is the probability distribution of crystal_growth?",
        target_node="crystal_growth",
        available_evidence=["thermal_flux", "growth_inhibitor"],
        correct_answer={"slow": 0.2, "medium": 0.3, "fast": 0.5},
        scoring_method="kl_divergence",
    )
    assert task.target_node == "crystal_growth"
    assert sum(task.correct_answer.values()) == 1.0


def test_task_serialization_roundtrip():
    task = Task(
        id="task-002",
        type=TaskType.NEXT_BEST_OBSERVATION,
        world_id="world-001",
        question="Which variable should you observe next?",
        target_node="crystal_growth",
        available_evidence=["thermal_flux"],
        correct_answer={"thermal_flux": 0.8, "inhibitor": 0.2},
        scoring_method="info_gain_ratio",
    )
    json_str = task.model_dump_json()
    restored = Task.model_validate_json(json_str)
    assert restored.id == task.id
    assert restored.correct_answer == task.correct_answer
