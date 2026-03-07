"""Tests for LLM Orchestrator — uses mocked OpenAI client."""

import json
from unittest.mock import MagicMock

from sreg.orchestrator.orchestrator import Orchestrator, OrchestratorResult
from sreg.orchestrator.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS

# --- Prompt and tool definitions ---


def test_system_prompt_not_empty():
    assert len(SYSTEM_PROMPT) > 100


def test_tool_definitions_complete():
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "world_gen" in names
    assert "world_check" in names
    assert "episode_gen" in names
    assert "task_gen" in names


def test_tool_definitions_have_required_fields():
    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert "required" in fn["parameters"]


# --- Tool dispatch (no LLM needed) ---


def test_dispatch_world_gen():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "world_gen",
        {
            "template_family": "latent_preference",
            "num_nodes": 6,
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert "world_id" in output
    assert output["num_nodes"] == 6
    assert result.world is not None
    assert result.attempts == 1


def test_dispatch_world_check():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    # First generate a world
    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )

    output = orch._dispatch_tool(
        "world_check",
        {"world_id": result.world.id},
        result,
    )

    assert output["passed"] is True
    assert result.validation_passed is True


def test_dispatch_world_check_unknown_world():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool("world_check", {"world_id": "nonexistent"}, result)
    assert "error" in output


def test_dispatch_episode_gen():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )

    output = orch._dispatch_tool(
        "episode_gen",
        {"world_id": result.world.id, "budget": 4},
        result,
    )

    assert output["budget"] == 4
    assert result.episode is not None


def test_dispatch_task_gen():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )

    output = orch._dispatch_tool(
        "task_gen",
        {"world_id": result.world.id, "task_type": "infer_target", "max_budget": 5},
        result,
    )

    assert output["task_id"] is not None
    assert output["type"] == "infer_target"
    assert result.task is not None


def test_dispatch_unknown_tool():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool("unknown_tool", {}, result)
    assert "error" in output


# --- Full orchestrator loop (mocked LLM) ---


def _make_mock_response(content=None, tool_calls=None, finish_reason="stop"):
    """Build a mock ChatCompletion response."""
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
    """Build a mock tool call."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def test_orchestrator_full_loop():
    """Simulate a full orchestrator loop with 3 tool calls then stop."""
    client = MagicMock()

    # Step 1: LLM calls world_gen
    resp1 = _make_mock_response(
        tool_calls=[
            _make_tool_call(
                "call_1",
                "world_gen",
                {
                    "template_family": "latent_preference",
                    "num_nodes": 6,
                    "edge_strength": 0.7,
                    "seed": 100,
                },
            )
        ],
        finish_reason="tool_calls",
    )

    # Step 2: LLM calls world_check
    resp2 = _make_mock_response(
        tool_calls=[_make_tool_call("call_2", "world_check", {"world_id": "world-000100"})],
        finish_reason="tool_calls",
    )

    # Step 3: LLM calls episode_gen and task_gen
    resp3 = _make_mock_response(
        tool_calls=[
            _make_tool_call("call_3", "episode_gen", {"world_id": "world-000100", "budget": 4}),
            _make_tool_call(
                "call_4",
                "task_gen",
                {"world_id": "world-000100", "task_type": "infer_target", "max_budget": 4},
            ),
        ],
        finish_reason="tool_calls",
    )

    # Step 4: LLM returns final summary
    resp4 = _make_mock_response(
        content=json.dumps(
            {
                "world_id": "world-000100",
                "template": "latent_preference",
                "num_nodes": 6,
                "difficulty": "easy",
                "validation_passed": True,
                "attempts": 1,
            }
        ),
        finish_reason="stop",
    )

    client.chat.completions.create.side_effect = [resp1, resp2, resp3, resp4]

    orch = Orchestrator(client=client, max_iterations=10)
    result = orch.run("Generate a medium-difficulty world for testing")

    assert result.world is not None
    assert result.validation_passed is True
    assert result.episode is not None
    assert result.task is not None
    assert result.attempts == 1
    assert len(result.messages) > 0

    # Verify the client was called 4 times
    assert client.chat.completions.create.call_count == 4


def test_orchestrator_retry_on_validation_failure():
    """Simulate: first world fails validation, LLM retries with new params."""
    client = MagicMock()

    # Step 1: LLM calls world_gen with very low edge_strength
    resp1 = _make_mock_response(
        tool_calls=[
            _make_tool_call(
                "call_1",
                "world_gen",
                {
                    "template_family": "latent_preference",
                    "num_nodes": 6,
                    "edge_strength": 0.5,
                    "seed": 200,
                },
            )
        ],
        finish_reason="tool_calls",
    )

    # Step 2: LLM calls world_check (will pass or fail, either way LLM "decides" to retry)
    resp2 = _make_mock_response(
        tool_calls=[_make_tool_call("call_2", "world_check", {"world_id": "world-000200"})],
        finish_reason="tool_calls",
    )

    # Step 3: LLM regenerates with different params
    resp3 = _make_mock_response(
        tool_calls=[
            _make_tool_call(
                "call_3",
                "world_gen",
                {
                    "template_family": "latent_preference",
                    "num_nodes": 7,
                    "edge_strength": 0.8,
                    "seed": 201,
                },
            )
        ],
        finish_reason="tool_calls",
    )

    # Step 4: Check passes
    resp4 = _make_mock_response(
        tool_calls=[_make_tool_call("call_4", "world_check", {"world_id": "world-000201"})],
        finish_reason="tool_calls",
    )

    # Step 5: Done
    resp5 = _make_mock_response(content="Done", finish_reason="stop")

    client.chat.completions.create.side_effect = [resp1, resp2, resp3, resp4, resp5]

    orch = Orchestrator(client=client, max_iterations=10)
    result = orch.run("Generate a world, retry if needed")

    assert result.attempts == 2
    assert result.validation_passed is True


def test_orchestrator_max_iterations():
    """Orchestrator respects max_iterations limit."""
    client = MagicMock()

    # LLM always calls a tool (never stops)
    resp = _make_mock_response(
        tool_calls=[
            _make_tool_call(
                "call_x",
                "world_gen",
                {
                    "template_family": "latent_preference",
                    "num_nodes": 6,
                    "edge_strength": 0.7,
                    "seed": 42,
                },
            )
        ],
        finish_reason="tool_calls",
    )
    client.chat.completions.create.return_value = resp

    orch = Orchestrator(client=client, max_iterations=3)
    orch.run("Generate endlessly")

    assert client.chat.completions.create.call_count == 3
