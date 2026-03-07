"""Tests for TaskGenTool."""

import pytest

from sreg.models.task import Task, TaskSpec, TaskType
from sreg.models.world import NodeType
from sreg.tools.task_gen import TaskGenTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


@pytest.fixture
def world():
    gen = WorldGenTool()
    return gen.generate(WorldGenConfig(seed=42, num_nodes=6, edge_strength=0.7))


def test_generate_infer_target_task(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert isinstance(task, Task)
    assert task.type == TaskType.INFER_TARGET
    assert task.world_id == world.id
    assert task.target_node == "target_outcome"


def test_task_has_correct_answer(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert isinstance(task.correct_answer, dict)
    assert abs(sum(task.correct_answer.values()) - 1.0) < 1e-6
    assert all(p >= 0 for p in task.correct_answer.values())


def test_task_available_evidence(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    obs_names = {n.name for n in world.nodes if n.type == NodeType.OBSERVABLE}
    assert set(task.available_evidence) == obs_names


def test_task_question_mentions_target(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert "target_outcome" in task.question


def test_task_question_mentions_budget(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=3)
    task = tool.generate(world, spec)

    assert "3" in task.question


def test_task_id_format(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.INFER_TARGET, target_node="target_outcome", max_budget=5)
    task = tool.generate(world, spec)

    assert task.id == f"task-{world.id}-infer_target"


def test_unsupported_task_type(world):
    tool = TaskGenTool()
    spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node="target_outcome", max_budget=5)
    with pytest.raises(ValueError, match="Unsupported task type"):
        tool.generate(world, spec)
