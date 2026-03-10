"""Tests for agent trajectory extraction, export, and comparison."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sreg.agent.agent import AgentResult
from sreg.harness.agent_trajectory import (
    export_agent_trajectories,
    extract_agent_trajectory,
)
from sreg.harness.comparison import compare_trajectories
from sreg.harness.trajectory import generate_teacher_trajectory
from sreg.models.research_problem import ResearchProblem
from sreg.models.score import Score
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world_and_problem(seed=42, num_nodes=6, budget=4):
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=seed, num_nodes=num_nodes))
    builder = ProblemBuilder()
    problem = builder.build(world, budget=budget)
    return world, problem


def _make_mock_agent_result(problem: ResearchProblem) -> AgentResult:
    """Build a fake AgentResult with realistic messages."""
    result = AgentResult()
    result.budget_total = problem.budget
    result.budget_used = 2

    # Pick two available nodes for observations
    nodes = [a.node for a in problem.available_actions]
    obs_node_1 = nodes[0] if nodes else "var_1"
    obs_node_2 = nodes[1] if len(nodes) > 1 else "var_2"

    target_states = problem.target_states
    dist = {s: 1.0 / len(target_states) for s in target_states}

    result.submitted_answer = dist
    result.confidence = 0.7
    result.reasoning = "Based on the observed correlations."
    result.observations = []  # simplified
    result.score = Score(
        functional_score=0.35,
        information_efficiency=0.5,
        budget_used=2,
        budget_total=problem.budget,
    )

    # Build realistic messages list
    result.messages = [
        {"role": "system", "content": "You are a research scientist..."},
        {"role": "user", "content": "Please analyze the data and solve this research problem."},
        # Iteration 1: agent thinks and observes
        {
            "role": "assistant",
            "content": (
                "Let me analyze the data. "
                "I'll start by observing the most informative variable."
            ),
            "tool_calls": [
                {
                    "id": "tc_001",
                    "type": "function",
                    "function": {
                        "name": "observe",
                        "arguments": json.dumps({"variable": obs_node_1}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_001",
            "content": json.dumps({
                "variable": obs_node_1,
                "observed_state": "high",
                "remaining_budget": problem.budget - 1,
                "message": f"{obs_node_1} was observed to be 'high'.",
            }),
        },
        # Iteration 2: agent observes again
        {
            "role": "assistant",
            "content": "Interesting. Now let me check another variable.",
            "tool_calls": [
                {
                    "id": "tc_002",
                    "type": "function",
                    "function": {
                        "name": "observe",
                        "arguments": json.dumps({"variable": obs_node_2}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_002",
            "content": json.dumps({
                "variable": obs_node_2,
                "observed_state": "low",
                "remaining_budget": problem.budget - 2,
                "message": f"{obs_node_2} was observed to be 'low'.",
            }),
        },
        # Iteration 3: agent submits
        {
            "role": "assistant",
            "content": "Based on my observations, I can now submit my answer.",
            "tool_calls": [
                {
                    "id": "tc_003",
                    "type": "function",
                    "function": {
                        "name": "submit",
                        "arguments": json.dumps({
                            "distribution": dist,
                            "confidence": 0.7,
                            "reasoning": "Based on the observed correlations.",
                        }),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_003",
            "content": json.dumps({
                "status": "submitted",
                "distribution": dist,
            }),
        },
    ]

    return result


def _make_mock_result_with_error(problem: ResearchProblem) -> AgentResult:
    """Build a fake AgentResult where one tool call fails."""
    result = AgentResult()
    result.budget_total = problem.budget
    result.budget_used = 1
    result.submitted_answer = {s: 1.0 / len(problem.target_states) for s in problem.target_states}
    result.score = Score(
        functional_score=0.8,
        information_efficiency=0.25,
        budget_used=1,
        budget_total=problem.budget,
    )

    result.messages = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        # Bad observe
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_err",
                    "type": "function",
                    "function": {
                        "name": "observe",
                        "arguments": json.dumps({"variable": "nonexistent_var"}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_err",
            "content": json.dumps({
                "error": "Variable 'nonexistent_var' is not available.",
            }),
        },
        # Then a good observe and submit
        {
            "role": "assistant",
            "content": "Let me try a valid variable.",
            "tool_calls": [
                {
                    "id": "tc_ok",
                    "type": "function",
                    "function": {
                        "name": "observe",
                        "arguments": json.dumps({
                            "variable": problem.available_actions[0].node,
                        }),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_ok",
            "content": json.dumps({
                "variable": problem.available_actions[0].node,
                "observed_state": "medium",
                "remaining_budget": problem.budget - 1,
            }),
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "tc_sub",
                    "type": "function",
                    "function": {
                        "name": "submit",
                        "arguments": json.dumps({
                            "distribution": result.submitted_answer,
                        }),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_sub",
            "content": json.dumps({"status": "submitted"}),
        },
    ]

    return result


def _make_no_submit_result(problem: ResearchProblem) -> AgentResult:
    """Build a fake AgentResult where the agent never submits."""
    result = AgentResult()
    result.budget_total = problem.budget
    result.budget_used = 0
    result.submitted_answer = None
    result.score = None

    result.messages = [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "I'm not sure what to do here."},
    ]

    return result


# ---------------------------------------------------------------------------
# Extraction tests
# ---------------------------------------------------------------------------


class TestExtractTrajectory:
    def test_basic_extraction(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem, world_id="test-001", seed=42)

        assert traj.world_id == "test-001"
        assert traj.seed == 42
        assert traj.target_node == problem.target_node
        assert traj.budget == problem.budget
        assert traj.budget_used == 2

    def test_step_count(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        # 2 observes + 1 submit = 3 tool call steps
        tool_steps = [s for s in traj.steps if s.tool_call is not None]
        assert len(tool_steps) == 3

    def test_thinking_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        # First step should have thinking
        assert traj.steps[0].thinking is not None
        assert "analyze" in traj.steps[0].thinking.lower()

    def test_observations_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        obs_steps = [s for s in traj.steps if s.observation is not None]
        assert len(obs_steps) == 2
        assert "= high" in obs_steps[0].observation
        assert "= low" in obs_steps[1].observation

    def test_submit_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        submit_steps = [s for s in traj.steps if s.is_submit]
        assert len(submit_steps) == 1
        assert traj.submitted_answer is not None

    def test_errors_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_result_with_error(problem)
        traj = extract_agent_trajectory(mock, problem)

        error_steps = [s for s in traj.steps if s.error is not None]
        assert len(error_steps) == 1
        assert "nonexistent_var" in error_steps[0].error

    def test_no_submit_result(self):
        _, problem = _make_world_and_problem()
        mock = _make_no_submit_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        assert traj.submitted_answer is None
        assert traj.score is None

    def test_score_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        assert traj.score is not None
        assert abs(traj.score - 0.35) < 0.001

    def test_tool_args_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        obs_steps = [s for s in traj.steps if s.tool_call == "observe"]
        assert len(obs_steps) == 2
        assert "variable" in obs_steps[0].tool_args

    def test_tool_result_captured(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        obs_steps = [s for s in traj.steps if s.tool_call == "observe"]
        assert obs_steps[0].tool_result is not None
        assert "observed_state" in obs_steps[0].tool_result


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_model_dump_serializable(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        d = traj.model_dump()
        json_str = json.dumps(d, default=str)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["target_node"] == problem.target_node

    def test_model_dump_json(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem)

        json_str = traj.model_dump_json()
        parsed = json.loads(json_str)
        assert len(parsed["steps"]) > 0

    def test_export_jsonl(self):
        _, problem = _make_world_and_problem()
        mock = _make_mock_agent_result(problem)
        traj = extract_agent_trajectory(mock, problem, world_id="w1")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = Path(f.name)

        export_agent_trajectories([traj], path)

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        d = json.loads(lines[0])
        assert d["world_id"] == "w1"
        assert len(d["steps"]) > 0

        path.unlink()

    def test_export_multiple(self):
        _, problem = _make_world_and_problem()
        mock1 = _make_mock_agent_result(problem)
        mock2 = _make_mock_result_with_error(problem)
        t1 = extract_agent_trajectory(mock1, problem, world_id="w1")
        t2 = extract_agent_trajectory(mock2, problem, world_id="w2")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            path = Path(f.name)

        export_agent_trajectories([t1, t2], path)

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2

        path.unlink()


# ---------------------------------------------------------------------------
# Comparison tests
# ---------------------------------------------------------------------------


class TestComparison:
    def test_basic_comparison(self):
        world, problem = _make_world_and_problem()
        teacher_traj = generate_teacher_trajectory(world, problem, seed=42)

        mock = _make_mock_agent_result(problem)
        agent_traj = extract_agent_trajectory(mock, problem, world_id=world.id, seed=42)

        comp = compare_trajectories(teacher_traj, agent_traj)

        assert comp.world_id == world.id
        assert comp.target_node == problem.target_node
        assert comp.true_state in problem.target_states
        assert len(comp.teacher_steps) > 0
        assert len(comp.agent_steps) > 0
        assert comp.teacher_final_posterior is not None
        assert comp.verdict in ("EXCELLENT", "GOOD", "FAIR", "POOR", "NO_SUBMIT", "NO_SCORE")

    def test_no_submit_verdict(self):
        world, problem = _make_world_and_problem()
        teacher_traj = generate_teacher_trajectory(world, problem, seed=42)

        mock = _make_no_submit_result(problem)
        agent_traj = extract_agent_trajectory(mock, problem, world_id=world.id)

        comp = compare_trajectories(teacher_traj, agent_traj)
        assert comp.verdict == "NO_SUBMIT"
        assert comp.agent_final_posterior is None

    def test_comparison_serializable(self):
        world, problem = _make_world_and_problem()
        teacher_traj = generate_teacher_trajectory(world, problem, seed=42)

        mock = _make_mock_agent_result(problem)
        agent_traj = extract_agent_trajectory(mock, problem, world_id=world.id)

        comp = compare_trajectories(teacher_traj, agent_traj)
        json_str = comp.model_dump_json()
        parsed = json.loads(json_str)
        assert "verdict" in parsed
        assert "teacher_steps" in parsed
        assert "agent_steps" in parsed

    def test_comparison_budget(self):
        world, problem = _make_world_and_problem()
        teacher_traj = generate_teacher_trajectory(world, problem, seed=42)

        mock = _make_mock_agent_result(problem)
        agent_traj = extract_agent_trajectory(mock, problem, world_id=world.id)

        comp = compare_trajectories(teacher_traj, agent_traj)
        assert comp.agent_budget_used == 2
        assert comp.teacher_budget_used == len(teacher_traj.steps)
