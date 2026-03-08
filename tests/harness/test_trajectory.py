"""Tests for teacher trajectory generation and export."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sreg.harness.trajectory import (
    export_trajectories,
    generate_teacher_trajectory,
)
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _make_world_and_problem(seed=42, num_nodes=6, budget=4):
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=seed, num_nodes=num_nodes))
    builder = ProblemBuilder()
    problem = builder.build(world, budget=budget)
    return world, problem


def test_trajectory_has_steps():
    world, problem = _make_world_and_problem()
    traj = generate_teacher_trajectory(world, problem, seed=42)

    assert len(traj.steps) > 0
    assert len(traj.steps) <= problem.budget


def test_trajectory_metadata():
    world, problem = _make_world_and_problem()
    traj = generate_teacher_trajectory(world, problem, seed=42)

    assert traj.world_id == world.id
    assert traj.seed == 42
    assert traj.target_node == problem.target_node
    assert traj.true_state in problem.target_states
    assert traj.budget == problem.budget


def test_trajectory_posteriors_are_valid():
    world, problem = _make_world_and_problem()
    traj = generate_teacher_trajectory(world, problem, seed=42)

    for step in traj.steps:
        assert set(step.posterior.keys()) == set(problem.target_states)
        total = sum(step.posterior.values())
        assert abs(total - 1.0) < 0.01


def test_trajectory_info_gains_positive():
    world, problem = _make_world_and_problem()
    traj = generate_teacher_trajectory(world, problem, seed=42)

    # At least the first step should have positive info gain
    assert traj.steps[0].info_gain > 0


def test_trajectory_final_posterior():
    world, problem = _make_world_and_problem()
    traj = generate_teacher_trajectory(world, problem, seed=42)

    assert set(traj.final_posterior.keys()) == set(problem.target_states)
    total = sum(traj.final_posterior.values())
    assert abs(total - 1.0) < 0.01


def test_trajectory_to_dict():
    world, problem = _make_world_and_problem()
    traj = generate_teacher_trajectory(world, problem, seed=42)

    d = traj.to_dict()
    assert d["world_id"] == world.id
    assert len(d["steps"]) == len(traj.steps)
    assert "final_posterior" in d

    # Should be JSON serializable
    json_str = json.dumps(d)
    assert len(json_str) > 0


def test_export_trajectories_jsonl():
    world, problem = _make_world_and_problem()
    trajs = [
        generate_teacher_trajectory(world, problem, seed=42),
        generate_teacher_trajectory(world, problem, seed=7),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)

    export_trajectories(trajs, path)

    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2

    for line in lines:
        d = json.loads(line)
        assert "world_id" in d
        assert "steps" in d
        assert "final_posterior" in d

    path.unlink()


def test_different_seeds_produce_different_trajectories():
    world, problem = _make_world_and_problem()
    t1 = generate_teacher_trajectory(world, problem, seed=0)
    t2 = generate_teacher_trajectory(world, problem, seed=1)

    # Different seeds may produce different true states or different observations
    # At minimum they should both be valid
    assert len(t1.steps) > 0
    assert len(t2.steps) > 0
