"""Tests for batch evaluation."""

from __future__ import annotations

from unittest.mock import MagicMock

from sreg.agent.agent import AgentResult
from sreg.harness.eval import BatchEvaluator, BatchResult, ProblemResult
from sreg.models.score import Score


def _mock_agent_result(submitted=True, kl=0.5, budget_used=3, budget_total=4):
    """Create a mock AgentResult."""
    result = AgentResult()
    if submitted:
        result.submitted_answer = {"low": 0.5, "medium": 0.3, "high": 0.2}
        result.score = Score(
            functional_score=kl,
            information_efficiency=0.5,
            budget_used=budget_used,
            budget_total=budget_total,
        )
    result.budget_used = budget_used
    result.budget_total = budget_total
    return result


def test_generate_problems():
    evaluator = BatchEvaluator()
    problems = evaluator.generate_problems(seeds=[0, 1, 2], num_nodes=5, budget=3)

    assert len(problems) == 3
    for world, problem in problems:
        assert len(world.nodes) == 5
        assert problem.budget == 3


def test_problem_result_beats_random():
    pr = ProblemResult(
        world_id="w1", seed=0, num_nodes=6, edge_strength=0.7,
        target_node="t", true_state="low", budget=4,
        agent_kl=0.3, random_kl=0.8,
    )
    assert pr.agent_beats_random is True

    pr2 = ProblemResult(
        world_id="w2", seed=1, num_nodes=6, edge_strength=0.7,
        target_node="t", true_state="low", budget=4,
        agent_kl=1.5, random_kl=0.8,
    )
    assert pr2.agent_beats_random is False


def test_problem_result_no_submission():
    pr = ProblemResult(
        world_id="w1", seed=0, num_nodes=6, edge_strength=0.7,
        target_node="t", true_state="low", budget=4,
        agent_kl=None, random_kl=0.8,
    )
    assert pr.agent_beats_random is None


def test_batch_result_summary():
    batch = BatchResult(results=[
        ProblemResult(
            world_id="w1", seed=0, num_nodes=6, edge_strength=0.7,
            target_node="t", true_state="low", budget=4,
            teacher_kl=0.0, agent_kl=0.3, random_kl=0.8,
            agent_submitted=True,
        ),
        ProblemResult(
            world_id="w2", seed=1, num_nodes=6, edge_strength=0.7,
            target_node="t", true_state="high", budget=4,
            teacher_kl=0.0, agent_kl=1.5, random_kl=0.9,
            agent_submitted=True,
        ),
    ])

    s = batch.summary()
    assert s["num_problems"] == 2
    assert s["num_submitted"] == 2
    assert s["num_beats_random"] == 1  # Only first beats random
    assert s["mean_teacher_kl"] == 0.0
    assert s["mean_agent_kl"] == 0.9  # (0.3 + 1.5) / 2
    assert s["mean_random_kl"] == 0.85  # (0.8 + 0.9) / 2


def test_evaluate_with_mock_agent():
    """Test full evaluation flow with a mocked agent."""
    mock_agent = MagicMock()
    mock_agent.solve.return_value = _mock_agent_result(submitted=True, kl=0.3)

    evaluator = BatchEvaluator(agent=mock_agent)
    problems = evaluator.generate_problems(seeds=[42], num_nodes=5, budget=3)
    batch = evaluator.evaluate(problems, seeds=[42])

    assert batch.num_problems == 1
    assert batch.num_submitted == 1
    assert batch.results[0].agent_kl == 0.3
    assert batch.results[0].teacher_kl == 0.0
    assert batch.results[0].random_kl > 0


def test_evaluate_agent_failure():
    """Agent throws exception — should be caught gracefully."""
    mock_agent = MagicMock()
    mock_agent.solve.side_effect = RuntimeError("LLM API error")

    evaluator = BatchEvaluator(agent=mock_agent)
    problems = evaluator.generate_problems(seeds=[42], num_nodes=5, budget=3)
    batch = evaluator.evaluate(problems, seeds=[42])

    assert batch.num_problems == 1
    assert batch.num_submitted == 0
    assert batch.results[0].agent_kl is None
