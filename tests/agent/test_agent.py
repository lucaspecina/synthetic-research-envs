"""Tests for LLM Agent solver — uses mocked OpenAI client."""

import json
from unittest.mock import MagicMock

from sreg.agent.agent import AgentResult, AgentSolver
from sreg.agent.prompts import AGENT_TOOL_DEFINITIONS, build_agent_system_prompt
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


# --- Tool dispatch (no LLM needed) ---


def test_dispatch_observe():
    world = _make_world()
    problem = _make_problem(world)

    agent = AgentSolver(client=MagicMock())
    result = AgentResult()
    result.budget_total = problem.budget

    # Set up runner
    from sreg.env.episode import EpisodeRunner
    from sreg.solver.exact_bayes import ExactBayesSolver
    from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=0)
    episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4, seed=0))
    runner = EpisodeRunner(world, episode, true_state)

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

    from sreg.env.episode import EpisodeRunner
    from sreg.solver.exact_bayes import ExactBayesSolver
    from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=0)
    episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4, seed=0))
    runner = EpisodeRunner(world, episode, true_state)

    output = agent._dispatch_tool(
        "observe", {"variable": "nonexistent"}, runner, problem, result
    )
    assert "error" in output


def test_dispatch_submit():
    world = _make_world()
    problem = _make_problem(world)

    agent = AgentSolver(client=MagicMock())
    result = AgentResult()

    from sreg.env.episode import EpisodeRunner
    from sreg.solver.exact_bayes import ExactBayesSolver
    from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=0)
    episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4, seed=0))
    runner = EpisodeRunner(world, episode, true_state)

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

    from sreg.env.episode import EpisodeRunner
    from sreg.solver.exact_bayes import ExactBayesSolver
    from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=0)
    episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4, seed=0))
    runner = EpisodeRunner(world, episode, true_state)

    output = agent._dispatch_tool(
        "submit", {"distribution": {"wrong": 1.0}}, runner, problem, result
    )
    assert "error" in output


def test_dispatch_unknown_tool():
    world = _make_world()
    problem = _make_problem(world)

    agent = AgentSolver(client=MagicMock())
    result = AgentResult()

    from sreg.env.episode import EpisodeRunner
    from sreg.solver.exact_bayes import ExactBayesSolver
    from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=0)
    episode = EpisodeGenTool().generate(world, EpisodeGenConfig(budget=4, seed=0))
    runner = EpisodeRunner(world, episode, true_state)

    output = agent._dispatch_tool("unknown", {}, runner, problem, result)
    assert "error" in output


# --- Full agent loop (mocked LLM) ---


def test_agent_observe_then_submit():
    """Simulate: agent observes one variable, then submits."""
    world = _make_world()
    problem = _make_problem(world)
    client = MagicMock()

    node = problem.available_actions[0].node
    target_states = problem.target_states
    dist = {s: 1.0 / len(target_states) for s in target_states}

    # Step 1: LLM calls observe
    resp1 = _make_mock_response(
        tool_calls=[_make_tool_call("call_1", "observe", {"variable": node})],
        finish_reason="tool_calls",
    )

    # Step 2: LLM calls submit
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

    # Should stop after 3 iterations (may observe fewer due to already-observed errors)
    assert client.chat.completions.create.call_count == 3
    assert result.submitted_answer is None
    assert result.score is None
