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
    assert "apply_semantics" in names
    assert "build_problem" in names


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


def test_dispatch_apply_semantics():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    # Generate a world first
    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )

    output = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": result.world.id,
            "scenario_title": "Coral Bleaching in the Nelvara Archipelago",
            "scenario_description": "Researchers studying coral health...",
            "domain": "marine ecology",
            "node_renames": {
                "hidden_cause": "water_acidity",
                "indicator_1": "coral_coverage",
                "indicator_2": "fish_diversity",
                "indicator_3": "algae_growth",
                "indicator_4": "sediment_level",
                "target_outcome": "bleaching_severity",
            },
            "node_descriptions": {
                "water_acidity": "pH levels measured at reef stations",
                "coral_coverage": "Percentage of live coral cover",
                "bleaching_severity": "Degree of coral bleaching observed",
            },
        },
        result,
    )

    assert output["scenario_title"] == "Coral Bleaching in the Nelvara Archipelago"
    assert output["domain"] == "marine ecology"
    assert output["nodes_renamed"] == 6
    # Verify the world was actually updated
    assert result.world.scenario_title == "Coral Bleaching in the Nelvara Archipelago"
    node_names = [n.name for n in result.world.nodes]
    assert "water_acidity" in node_names
    assert "hidden_cause" not in node_names


def test_dispatch_apply_semantics_empty_renames():
    """apply_semantics rejects empty node_renames with an error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )

    output = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": result.world.id,
            "scenario_title": "X",
            "scenario_description": "X",
            "domain": "X",
            "node_renames": {},
        },
        result,
    )
    assert "error" in output
    assert "node_renames is empty" in output["error"]


def test_dispatch_apply_semantics_unknown_world():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": "nonexistent",
            "scenario_title": "X",
            "scenario_description": "X",
            "domain": "X",
            "node_renames": {"a": "b"},
        },
        result,
    )
    assert "error" in output


def _full_renames() -> dict[str, str]:
    """Standard renames for a 6-node latent_preference world."""
    return {
        "hidden_cause": "soil_acidity",
        "indicator_1": "water_ph",
        "indicator_2": "nitrogen_level",
        "indicator_3": "microbial_count",
        "indicator_4": "root_depth",
        "target_outcome": "crop_yield",
    }


def test_dispatch_build_problem():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    # Generate and enrich a world
    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )
    orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": result.world.id,
            "scenario_title": "Test Problem",
            "scenario_description": "A test scenario.",
            "domain": "testing",
            "node_renames": _full_renames(),
            "node_descriptions": {},
        },
        result,
    )

    output = orch._dispatch_tool(
        "build_problem",
        {"world_id": result.world.id, "budget": 4, "data_format": "tabular"},
        result,
    )

    assert output["title"] == "Test Problem"
    assert output["budget"] == 4
    assert output["num_data_assets"] == 1
    assert output["num_actions"] > 0
    assert result.problem is not None
    assert result.problem.budget == 4


def test_dispatch_build_problem_unknown_world():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "build_problem",
        {"world_id": "nonexistent", "budget": 5, "data_format": "tabular"},
        result,
    )
    assert "error" in output


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


# --- dag_generate tool ---


def test_tool_definitions_include_dag_tools():
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "dag_generate" in names
    assert "dag_construct" in names


def test_dispatch_dag_generate_erdos_renyi():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_generate",
        {"generator": "erdos_renyi", "num_nodes": 8, "edge_strength": 0.7, "seed": 42},
        result,
    )

    assert "world_id" in output
    assert output["generator"] == "erdos_renyi"
    assert output["num_nodes"] == 8
    assert result.world is not None


def test_dispatch_dag_generate_spanning_tree():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_generate",
        {
            "generator": "spanning_tree",
            "num_nodes": 10,
            "extra_edge_prob": 0.15,
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert output["num_nodes"] == 10
    assert output["generator"] == "spanning_tree"


def test_dispatch_dag_generate_preferential_attachment():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_generate",
        {
            "generator": "preferential_attachment",
            "num_nodes": 10,
            "num_edges_per_node": 2,
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert output["num_nodes"] == 10
    assert output["generator"] == "preferential_attachment"


def test_dispatch_dag_generate_layered():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_generate",
        {
            "generator": "layered",
            "num_layers": 3,
            "nodes_per_layer": 3,
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert output["num_nodes"] == 9
    assert output["generator"] == "layered"


def test_dispatch_dag_generate_unknown_generator():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_generate",
        {"generator": "nonexistent", "edge_strength": 0.7, "seed": 42},
        result,
    )

    assert "error" in output
    assert "nonexistent" in output["error"]


def test_dispatch_dag_generate_with_latents():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_generate",
        {
            "generator": "erdos_renyi",
            "num_nodes": 10,
            "num_latent": 2,
            "num_target": 1,
            "edge_prob": 0.3,
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert output["num_nodes"] == 10
    latent_count = sum(1 for n in output["nodes"] if n["type"] == "latent")
    assert latent_count == 2


# --- dag_construct tool ---


def test_dispatch_dag_construct_basic():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_construct",
        {
            "nodes": [
                {"name": "cause", "type": "latent", "states": ["on", "off"]},
                {"name": "sensor_a", "type": "observable", "states": ["low", "high"]},
                {"name": "sensor_b", "type": "observable", "states": ["low", "high"]},
                {"name": "outcome", "type": "target", "states": ["bad", "good"]},
            ],
            "edges": [
                {"from": "cause", "to": "sensor_a"},
                {"from": "cause", "to": "sensor_b"},
                {"from": "sensor_a", "to": "outcome"},
            ],
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert "world_id" in output
    assert output["num_nodes"] == 4
    assert result.world is not None
    node_names = [n["name"] for n in output["nodes"]]
    assert "cause" in node_names
    assert "outcome" in node_names


def test_dispatch_dag_construct_invalid_cycle():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_construct",
        {
            "nodes": [
                {"name": "a", "type": "observable", "states": ["x", "y"]},
                {"name": "b", "type": "observable", "states": ["x", "y"]},
                {"name": "c", "type": "target", "states": ["x", "y"]},
            ],
            "edges": [
                {"from": "a", "to": "b"},
                {"from": "b", "to": "c"},
                {"from": "c", "to": "a"},
            ],
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert "error" in output


def test_dispatch_dag_construct_no_target():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_construct",
        {
            "nodes": [
                {"name": "a", "type": "observable", "states": ["x", "y"]},
                {"name": "b", "type": "observable", "states": ["x", "y"]},
            ],
            "edges": [{"from": "a", "to": "b"}],
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert "error" in output


def test_dispatch_dag_construct_empty_nodes():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_construct",
        {"nodes": [], "edges": [], "edge_strength": 0.7, "seed": 42},
        result,
    )

    assert "error" in output


def test_dispatch_dag_construct_empty_edges():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "dag_construct",
        {
            "nodes": [
                {"name": "a", "type": "observable", "states": ["x", "y"]},
                {"name": "b", "type": "target", "states": ["x", "y"]},
            ],
            "edges": [],
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    assert "error" in output


# --- dag tools + downstream pipeline ---


def test_dag_generate_then_world_check():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    gen_output = orch._dispatch_tool(
        "dag_generate",
        {"generator": "spanning_tree", "num_nodes": 8, "edge_strength": 0.7, "seed": 42},
        result,
    )

    check_output = orch._dispatch_tool(
        "world_check",
        {"world_id": gen_output["world_id"]},
        result,
    )

    assert check_output["passed"] is True


def test_dag_construct_then_apply_semantics():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    gen_output = orch._dispatch_tool(
        "dag_construct",
        {
            "nodes": [
                {"name": "hidden", "type": "latent", "states": ["a", "b"]},
                {"name": "obs1", "type": "observable", "states": ["low", "high"]},
                {"name": "obs2", "type": "observable", "states": ["low", "high"]},
                {"name": "target", "type": "target", "states": ["bad", "good"]},
            ],
            "edges": [
                {"from": "hidden", "to": "obs1"},
                {"from": "hidden", "to": "obs2"},
                {"from": "obs1", "to": "target"},
            ],
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )

    sem_output = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": gen_output["world_id"],
            "scenario_title": "Test",
            "scenario_description": "A test.",
            "domain": "testing",
            "node_renames": {
                "hidden": "soil_type",
                "obs1": "ph_level",
                "obs2": "moisture",
                "target": "crop_yield",
            },
            "node_descriptions": {},
        },
        result,
    )

    assert "error" not in sem_output
    assert sem_output["nodes_renamed"] == 4
    node_names = [n["name"] for n in sem_output["nodes"]]
    assert "soil_type" in node_names


def test_dag_generate_full_pipeline():
    """dag_generate -> world_check -> apply_semantics -> build_problem."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    # Step 1: Generate
    gen_out = orch._dispatch_tool(
        "dag_generate",
        {
            "generator": "layered",
            "num_layers": 3,
            "nodes_per_layer": 2,
            "num_latent": 1,
            "edge_strength": 0.7,
            "seed": 42,
        },
        result,
    )
    world_id = gen_out["world_id"]

    # Step 2: Check
    check_out = orch._dispatch_tool("world_check", {"world_id": world_id}, result)
    assert check_out["passed"] is True

    # Step 3: Apply semantics (rename v0..v5)
    renames = {}
    names = ["hidden_factor", "temp_reading", "pressure", "humidity", "wind_speed", "forecast"]
    for i, n in enumerate(gen_out["nodes"]):
        renames[n["name"]] = names[i]

    sem_out = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Weather Prediction",
            "scenario_description": "A weather forecasting problem.",
            "domain": "meteorology",
            "node_renames": renames,
            "node_descriptions": {},
        },
        result,
    )
    assert "error" not in sem_out

    # Step 4: Build problem
    prob_out = orch._dispatch_tool(
        "build_problem",
        {"world_id": world_id, "budget": 3, "data_format": "tabular"},
        result,
    )
    assert prob_out["title"] == "Weather Prediction"
    assert prob_out["budget"] == 3
    assert result.problem is not None
