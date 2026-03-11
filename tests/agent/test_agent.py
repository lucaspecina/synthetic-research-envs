"""Tests for LLM Agent solver — uses mocked OpenAI client."""

import json
from unittest.mock import MagicMock

from sreg.agent.agent import AgentResult, AgentSolver
from sreg.agent.prompts import (
    AGENT_TOOL_DEFINITIONS,
    build_agent_system_prompt,
    build_agent_tools,
    build_submit_tool,
)
from sreg.models.task import Task, TaskType
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

# --- Fixtures ---


def _make_world(seed=42):
    gen = WorldGenTool()
    return gen.generate(WorldGenConfig(seed=seed, num_nodes=6, edge_strength=0.7))


def _make_problem(world):
    builder = ProblemBuilder()
    return builder.build(world, budget=4)


def _make_mock_response(content=None, tool_calls=None, finish_reason="stop"):
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = finish_reason

    response = MagicMock()
    response.choices = [choice]
    return response


def _make_tool_call(call_id, name, args):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def _make_task(task_type, correct_answer, **kwargs):
    """Create a minimal Task for testing."""
    return Task(
        id=f"test-{task_type}",
        type=task_type,
        world_id="test-world",
        question=f"Test question for {task_type}",
        target_node="target",
        available_evidence=["a", "b", "c"],
        correct_answer=correct_answer,
        **kwargs,
    )


# --- Prompt and tool definitions ---


def test_agent_tool_definitions_complete():
    names = {t["function"]["name"] for t in AGENT_TOOL_DEFINITIONS}
    assert "observe" in names
    assert "submit" in names


def test_agent_tool_definitions_have_required_fields():
    for tool in AGENT_TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn


def test_system_prompt_contains_problem_info():
    world = _make_world()
    problem = _make_problem(world)
    prompt = build_agent_system_prompt(problem)

    assert problem.title in prompt
    assert problem.target_node in prompt
    assert "budget" in prompt.lower()
    assert "submit" in prompt.lower()


def test_system_prompt_lists_available_actions():
    world = _make_world()
    problem = _make_problem(world)
    prompt = build_agent_system_prompt(problem)

    for action in problem.available_actions:
        assert action.node in prompt


def test_system_prompt_lists_target_states():
    world = _make_world()
    problem = _make_problem(world)
    prompt = build_agent_system_prompt(problem)

    for state in problem.target_states:
        assert state in prompt


# --- Submit tool generation per task type ---


def test_submit_tool_distribution_default():
    """No task = distribution submit (backward compat)."""
    tool = build_submit_tool(target_states=["low", "high"])
    props = tool["function"]["parameters"]["properties"]
    assert "distribution" in props
    assert tool["function"]["parameters"]["required"] == ["distribution"]


def test_submit_tool_choice_hypothesis():
    task = _make_task(
        TaskType.HYPOTHESIS_SELECTION,
        {"A": 0.0, "B": 1.0, "C": 0.5},
        hypotheses={"A": {"x": 0.5}, "B": {"x": 0.8}, "C": {"x": 0.2}},
    )
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "choice" in props
    assert "distribution" not in props
    assert tool["function"]["parameters"]["required"] == ["choice"]


def test_submit_tool_choice_compare():
    task = _make_task(
        TaskType.COMPARE_INTERVENTIONS,
        {"node_a:state_a": 0.8, "node_b:state_b": 0.3},
    )
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "choice" in props
    assert props["choice"]["enum"] == ["A", "B"]


def test_submit_tool_choice_should_condition():
    task = _make_task(TaskType.SHOULD_CONDITION, {"yes": 1.0})
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "choice" in props
    assert set(props["choice"]["enum"]) == {"yes", "no"}


def test_submit_tool_intervention():
    task = _make_task(
        TaskType.BEST_INTERVENTION,
        {"temp:high": 0.9, "pressure:low": 0.4},
    )
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "node" in props
    assert "state" in props
    assert "distribution" not in props


def test_submit_tool_variable_set():
    task = _make_task(TaskType.ADJUSTMENT_SET, {"age,income": 1.0})
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "variables" in props
    assert "not_identifiable" in props
    assert "distribution" not in props


def test_submit_tool_causal_effect_is_distribution():
    task = _make_task(TaskType.CAUSAL_EFFECT, {"low": 0.3, "high": 0.7})
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "distribution" in props


def test_build_agent_tools_returns_observe_and_submit():
    tools = build_agent_tools()
    names = {t["function"]["name"] for t in tools}
    assert names == {"observe", "submit"}


# --- System prompt with task ---


def test_system_prompt_with_task_uses_task_question():
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(
        TaskType.SHOULD_CONDITION,
        {"no": 1.0},
    )
    task.question = "Should you control for Z when analyzing X's effect on Y?"
    prompt = build_agent_system_prompt(problem, task=task)
    assert "Should you control for Z" in prompt


def test_system_prompt_choice_type_no_distribution_instruction():
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(TaskType.COMPARE_INTERVENTIONS, {"a:x": 0.8, "b:y": 0.3})
    prompt = build_agent_system_prompt(problem, task=task)
    # Should mention choice, not distribution
    assert "choice" in prompt.lower()


def test_system_prompt_intervention_type():
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(TaskType.BEST_INTERVENTION, {"t:h": 0.9})
    prompt = build_agent_system_prompt(problem, task=task)
    assert "node" in prompt.lower()
    assert "state" in prompt.lower()


# --- Tool dispatch (no LLM needed) ---


def _make_runner(world, seed=0, budget=4):
    from sreg.env.episode import EpisodeRunner
    from sreg.solver.exact_bayes import ExactBayesSolver
    from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)
    episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=budget, seed=seed))
    return EpisodeRunner(world, episode, true_state)


def test_dispatch_observe():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget
    runner = _make_runner(world)

    node = problem.available_actions[0].node
    output = agent._dispatch_tool("observe", {"variable": node}, runner, problem, result)

    assert "observed_state" in output
    assert output["variable"] == node
    assert result.budget_used == 1
    assert len(result.observations) == 1


def test_dispatch_observe_invalid_variable():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)

    output = agent._dispatch_tool(
        "observe", {"variable": "nonexistent"}, runner, problem, result
    )
    assert "error" in output


def test_dispatch_submit():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)

    dist = {s: 1.0 / len(problem.target_states) for s in problem.target_states}
    output = agent._dispatch_tool(
        "submit", {"distribution": dist, "confidence": 0.5}, runner, problem, result
    )

    assert output["status"] == "submitted"
    assert result.submitted_answer is not None
    assert result.confidence == 0.5
    assert runner.is_finished


def test_dispatch_submit_wrong_states():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)

    output = agent._dispatch_tool(
        "submit", {"distribution": {"wrong": 1.0}}, runner, problem, result
    )
    assert "error" in output


def test_dispatch_unknown_tool():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)

    output = agent._dispatch_tool("unknown", {}, runner, problem, result)
    assert "error" in output


# --- Multi-type submit dispatch ---


def test_dispatch_submit_choice():
    """Submit a choice (compare_interventions)."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.COMPARE_INTERVENTIONS, {"a:x": 0.8, "b:y": 0.3})

    output = agent._dispatch_tool(
        "submit", {"choice": "A", "reasoning": "A is better"}, runner, problem, result, task
    )
    assert output["status"] == "submitted"
    assert result.submitted_answer == "A"
    assert result.reasoning == "A is better"


def test_dispatch_submit_choice_missing():
    """Submit choice without the key returns error."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.SHOULD_CONDITION, {"yes": 1.0})

    output = agent._dispatch_tool(
        "submit", {"reasoning": "I think so"}, runner, problem, result, task
    )
    assert "error" in output


def test_dispatch_submit_intervention():
    """Submit an intervention (best_intervention)."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.BEST_INTERVENTION, {"temp:high": 0.9})

    output = agent._dispatch_tool(
        "submit", {"node": "temp", "state": "high"}, runner, problem, result, task
    )
    assert output["status"] == "submitted"
    assert result.submitted_answer == {"node": "temp", "state": "high"}


def test_dispatch_submit_intervention_missing_state():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.BEST_INTERVENTION, {"temp:high": 0.9})

    output = agent._dispatch_tool(
        "submit", {"node": "temp"}, runner, problem, result, task
    )
    assert "error" in output


def test_dispatch_submit_variable_set():
    """Submit a variable set (adjustment_set)."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.ADJUSTMENT_SET, {"age,income": 1.0})

    output = agent._dispatch_tool(
        "submit", {"variables": ["income", "age"]}, runner, problem, result, task
    )
    assert output["status"] == "submitted"
    assert result.submitted_answer == ["age", "income"]  # sorted


def test_dispatch_submit_variable_set_empty():
    """Submit empty variable set (no confounding)."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.ADJUSTMENT_SET, {"_empty_": 1.0})

    output = agent._dispatch_tool(
        "submit", {"variables": []}, runner, problem, result, task
    )
    assert output["status"] == "submitted"
    assert result.submitted_answer == []


def test_dispatch_submit_not_identifiable():
    """Submit not_identifiable for adjustment_set."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(TaskType.ADJUSTMENT_SET, {"_not_identifiable_": 1.0})

    output = agent._dispatch_tool(
        "submit", {"variables": [], "not_identifiable": True}, runner, problem, result, task
    )
    assert output["status"] == "submitted"
    assert result.submitted_answer == "_not_identifiable_"


# --- Scoring per task type ---


def test_score_distribution_type():
    """Score for infer_target uses KL divergence."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget
    runner = _make_runner(world)

    dist = {s: 1.0 / len(problem.target_states) for s in problem.target_states}
    agent._dispatch_tool("submit", {"distribution": dist}, runner, problem, result)
    score = agent._score_result(result, None, problem, runner)
    assert score.functional_score >= 0


def test_score_choice_correct():
    """Score for compare_interventions — correct choice."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = "A"
    task = _make_task(
        TaskType.COMPARE_INTERVENTIONS,
        {"node_a:state_a": 0.8, "node_b:state_b": 0.3},
    )
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 1.0


def test_score_choice_wrong():
    """Score for compare_interventions — wrong choice."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = "B"
    task = _make_task(
        TaskType.COMPARE_INTERVENTIONS,
        {"node_a:state_a": 0.8, "node_b:state_b": 0.3},
    )
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 0.0


def test_score_should_condition():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = "yes"
    task = _make_task(TaskType.SHOULD_CONDITION, {"yes": 1.0})
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 1.0


def test_score_best_intervention():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = {"node": "temp", "state": "high"}
    task = _make_task(
        TaskType.BEST_INTERVENTION,
        {"temp:high": 0.9, "pressure:low": 0.4},
    )
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 1.0  # chose the best one


def test_score_adjustment_set_correct():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = ["age", "income"]
    task = _make_task(TaskType.ADJUSTMENT_SET, {"age,income": 1.0})
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 1.0


def test_score_adjustment_set_wrong():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = ["wrong_var"]
    task = _make_task(TaskType.ADJUSTMENT_SET, {"age,income": 1.0})
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 0.0


def test_score_not_identifiable():
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = "_not_identifiable_"
    task = _make_task(TaskType.ADJUSTMENT_SET, {"_not_identifiable_": 1.0})
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 1.0


# --- Full agent loop (mocked LLM) ---


def test_agent_observe_then_submit():
    """Simulate: agent observes one variable, then submits."""
    world = _make_world()
    problem = _make_problem(world)
    client = MagicMock()

    node = problem.available_actions[0].node
    target_states = problem.target_states
    dist = {s: 1.0 / len(target_states) for s in target_states}

    resp1 = _make_mock_response(
        tool_calls=[_make_tool_call("call_1", "observe", {"variable": node})],
        finish_reason="tool_calls",
    )
    resp2 = _make_mock_response(
        tool_calls=[
            _make_tool_call(
                "call_2", "submit", {"distribution": dist, "confidence": 0.6}
            )
        ],
        finish_reason="tool_calls",
    )

    client.chat.completions.create.side_effect = [resp1, resp2]

    agent = AgentSolver(client=client, max_iterations=10)
    result = agent.solve(world, problem, seed=0)

    assert result.submitted_answer is not None
    assert result.budget_used == 1
    assert result.score is not None
    assert result.score.functional_score >= 0
    assert len(result.observations) == 1


def test_agent_direct_submit():
    """Agent submits immediately without observing."""
    world = _make_world()
    problem = _make_problem(world)
    client = MagicMock()

    target_states = problem.target_states
    dist = {s: 1.0 / len(target_states) for s in target_states}

    resp = _make_mock_response(
        tool_calls=[_make_tool_call("call_1", "submit", {"distribution": dist})],
        finish_reason="tool_calls",
    )
    client.chat.completions.create.side_effect = [resp]

    agent = AgentSolver(client=client, max_iterations=10)
    result = agent.solve(world, problem, seed=0)

    assert result.submitted_answer is not None
    assert result.budget_used == 0
    assert result.score is not None


def test_agent_max_iterations():
    """Agent respects max_iterations when it never submits."""
    world = _make_world()
    problem = _make_problem(world)
    client = MagicMock()

    node = problem.available_actions[0].node

    resp = _make_mock_response(
        tool_calls=[_make_tool_call("call_x", "observe", {"variable": node})],
        finish_reason="tool_calls",
    )
    client.chat.completions.create.return_value = resp

    agent = AgentSolver(client=client, max_iterations=3)
    result = agent.solve(world, problem, seed=0)

    assert client.chat.completions.create.call_count == 3
    assert result.submitted_answer is None
    assert result.score is None


def test_agent_solve_with_choice_task():
    """Full loop: agent submits a choice for should_condition."""
    world = _make_world()
    problem = _make_problem(world)
    client = MagicMock()
    task = _make_task(TaskType.SHOULD_CONDITION, {"no": 1.0})

    resp = _make_mock_response(
        tool_calls=[
            _make_tool_call("call_1", "submit", {"choice": "no", "reasoning": "It's a mediator"})
        ],
        finish_reason="tool_calls",
    )
    client.chat.completions.create.side_effect = [resp]

    agent = AgentSolver(client=client, max_iterations=10)
    result = agent.solve(world, problem, seed=0, task=task)

    assert result.submitted_answer == "no"
    assert result.score is not None
    assert result.score.functional_score == 1.0
    assert result.task_type == TaskType.SHOULD_CONDITION


def test_agent_solve_with_intervention_task():
    """Full loop: agent submits an intervention for best_intervention."""
    world = _make_world()
    problem = _make_problem(world)
    client = MagicMock()
    task = _make_task(
        TaskType.BEST_INTERVENTION,
        {"temp:high": 0.9, "pressure:low": 0.4},
    )

    resp = _make_mock_response(
        tool_calls=[
            _make_tool_call("call_1", "submit", {"node": "temp", "state": "high"})
        ],
        finish_reason="tool_calls",
    )
    client.chat.completions.create.side_effect = [resp]

    agent = AgentSolver(client=client, max_iterations=10)
    result = agent.solve(world, problem, seed=0, task=task)

    assert result.submitted_answer == {"node": "temp", "state": "high"}
    assert result.score is not None
    assert result.score.functional_score == 1.0


# --- NBO: choice of variable, scored by IG ratio ---


def test_submit_tool_nbo_is_choice():
    """NBO submit tool should be a choice among variable names."""
    task = _make_task(
        TaskType.NEXT_BEST_OBSERVATION,
        {"var_a": 0.8, "var_b": 0.2, "var_c": 0.0},
    )
    tool = build_submit_tool(task)
    props = tool["function"]["parameters"]["properties"]
    assert "choice" in props
    assert "distribution" not in props
    assert set(props["choice"]["enum"]) == {"var_a", "var_b", "var_c"}


def test_dispatch_submit_nbo_choice():
    """NBO submit dispatches to choice handler."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    runner = _make_runner(world)
    task = _make_task(
        TaskType.NEXT_BEST_OBSERVATION,
        {"var_a": 0.8, "var_b": 0.2},
    )

    output = agent._dispatch_tool(
        "submit", {"choice": "var_a"}, runner, problem, result, task
    )
    assert output["status"] == "submitted"
    assert result.submitted_answer == "var_a"


def test_score_nbo_optimal():
    """NBO scoring: choosing best variable -> 1.0."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = "var_a"
    task = _make_task(
        TaskType.NEXT_BEST_OBSERVATION,
        {"var_a": 0.8, "var_b": 0.2, "var_c": 0.0},
    )
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 1.0


def test_score_nbo_suboptimal():
    """NBO scoring: choosing suboptimal variable -> ratio."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.submitted_answer = "var_b"
    task = _make_task(
        TaskType.NEXT_BEST_OBSERVATION,
        {"var_a": 0.8, "var_b": 0.2, "var_c": 0.0},
    )
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score == 0.25  # 0.2 / 0.8


# --- Distribution types: scoring uses task.correct_answer ---


def test_score_causal_effect_uses_task_answer():
    """causal_effect scoring should use task.correct_answer, not runner posterior."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget
    # Agent submits exactly the task's correct answer
    correct = {"low": 0.3, "medium": 0.5, "high": 0.2}
    result.submitted_answer = correct.copy()
    task = _make_task(TaskType.CAUSAL_EFFECT, correct)
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    # KL of identical distributions should be ~0
    assert score.functional_score < 0.01


def test_score_infer_latent_cause_uses_task_answer():
    """infer_latent_cause scoring uses task.correct_answer (latent posterior)."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget
    correct = {"hidden_low": 0.7, "hidden_high": 0.3}
    result.submitted_answer = correct.copy()
    task = _make_task(
        TaskType.INFER_LATENT_CAUSE,
        correct,
    )
    task.target_node = "hidden_factor"  # different from problem.target_node
    runner = _make_runner(world)
    score = agent._score_result(result, task, problem, runner)
    assert score.functional_score < 0.01


# --- System prompt: task target node ---


def test_system_prompt_infer_latent_cause_uses_task_target():
    """infer_latent_cause prompt should show task's target (latent), not problem's."""
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(
        TaskType.INFER_LATENT_CAUSE,
        {"hidden_low": 0.7, "hidden_high": 0.3},
    )
    task.target_node = "hidden_factor"
    prompt = build_agent_system_prompt(problem, task=task)
    assert "hidden_factor" in prompt
    assert "hidden_low" in prompt
    assert "hidden_high" in prompt


# --- Bug fix: prompt states_str only for distribution types ---


def test_system_prompt_nbo_does_not_show_answer_keys_as_states():
    """NBO correct_answer keys are variables, not 'possible states'."""
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(
        TaskType.NEXT_BEST_OBSERVATION,
        {"var_a": 0.8, "var_b": 0.2},
    )
    prompt = build_agent_system_prompt(problem, task=task)
    # The prompt should NOT say "possible states: var_a, var_b"
    # It should still show problem.target_states
    assert "var_a, var_b" not in prompt
    for s in problem.target_states:
        assert s in prompt


def test_system_prompt_hypothesis_does_not_show_labels_as_states():
    """hypothesis_selection correct_answer keys are labels, not states."""
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(
        TaskType.HYPOTHESIS_SELECTION,
        {"A": 1.0},
        hypotheses={"A": {"x": 0.9, "y": 0.1}, "B": {"x": 0.4, "y": 0.6}},
    )
    prompt = build_agent_system_prompt(problem, task=task)
    for s in problem.target_states:
        assert s in prompt


def test_system_prompt_should_condition_does_not_show_yesno_as_states():
    """should_condition correct_answer has yes/no — not target states."""
    world = _make_world()
    problem = _make_problem(world)
    task = _make_task(TaskType.SHOULD_CONDITION, {"yes": 1.0})
    prompt = build_agent_system_prompt(problem, task=task)
    # "possible states" line should have the real states, not "yes"
    for s in problem.target_states:
        assert s in prompt


# --- Bug fix: _submit_distribution validates against task states ---


def test_submit_distribution_uses_task_states():
    """infer_latent_cause: submit validates against task answer keys, not problem."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget
    runner = _make_runner(world)
    task = _make_task(
        TaskType.INFER_LATENT_CAUSE,
        {"hidden_low": 0.7, "hidden_high": 0.3},
    )
    # Submit with task-specific states (not problem.target_states)
    output = agent._dispatch_tool(
        "submit",
        {"distribution": {"hidden_low": 0.6, "hidden_high": 0.4}},
        runner, problem, result, task,
    )
    assert "error" not in output
    assert output["status"] == "submitted"


def test_submit_distribution_rejects_problem_states_for_latent():
    """If task has different states, submitting problem.target_states should fail."""
    world = _make_world()
    problem = _make_problem(world)
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget
    runner = _make_runner(world)
    task = _make_task(
        TaskType.INFER_LATENT_CAUSE,
        {"hidden_low": 0.7, "hidden_high": 0.3},
    )
    # Submit using problem.target_states — should be rejected
    wrong_dist = {s: 1.0 / len(problem.target_states) for s in problem.target_states}
    output = agent._dispatch_tool(
        "submit",
        {"distribution": wrong_dist},
        runner, problem, result, task,
    )
    assert "error" in output


# --- Bug fix: NBO error message ---


def test_submit_choice_nbo_error_message():
    """NBO missing choice should show variable-specific error, not yes/no."""
    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    output = agent._submit_choice({}, result, TaskType.NEXT_BEST_OBSERVATION)
    assert "error" in output
    assert "variable" in output["error"].lower()
    assert "yes" not in output["error"].lower()
