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
    assert "scm_construct" in names
    assert "world_check" in names
    assert "apply_semantics" in names
    assert "design_case" in names
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


def test_dispatch_apply_semantics_empty_renames_autocompletes():
    """apply_semantics auto-completes identity mappings when node_renames is empty."""
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
    # Should succeed (auto-completed), not error
    assert "error" not in output
    assert output["nodes_renamed"] > 0


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
    assert output["num_data_assets"] >= 1  # multi_dataset produces 2-3 artifacts
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
    """Build a mock Responses API response."""
    output = []
    if content:
        text_part = MagicMock()
        text_part.text = content
        msg_item = MagicMock()
        msg_item.type = "message"
        msg_item.content = [text_part]
        output.append(msg_item)
    if tool_calls:
        output.extend(tool_calls)

    response = MagicMock()
    response.output = output
    response.id = f"resp-{id(response)}"
    response.status = "completed"
    return response


def _make_tool_call(call_id, name, args):
    """Build a mock function_call output item (Responses API format)."""
    tc = MagicMock()
    tc.type = "function_call"
    tc.call_id = call_id
    tc.name = name
    tc.arguments = json.dumps(args)
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

    client.responses.create.side_effect = [resp1, resp2, resp3, resp4]

    orch = Orchestrator(client=client, max_iterations=10)
    result = orch.run("Generate a medium-difficulty world for testing")

    assert result.world is not None
    assert result.validation_passed is True
    assert result.episode is not None
    assert result.task is not None
    assert result.attempts == 1
    assert len(result.messages) > 0

    # Verify the client was called 4 times
    assert client.responses.create.call_count == 4


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

    client.responses.create.side_effect = [resp1, resp2, resp3, resp4, resp5]

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
    client.responses.create.return_value = resp

    orch = Orchestrator(client=client, max_iterations=3)
    orch.run("Generate endlessly")

    assert client.responses.create.call_count == 3


# --- dag_generate tool ---


def test_tool_definitions_include_scm_tool():
    """BN tools removed from TOOL_DEFINITIONS; only SCM exposed."""
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "scm_construct" in names
    # BN tools still work via handlers but are not exposed to the LLM
    assert "dag_generate" not in names
    assert "dag_construct" not in names
    assert "world_gen" not in names


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


# --- design_case tool ---


def _setup_world_with_semantics(orch, result):
    """Helper: generate a world and apply semantics, return world_id."""
    orch._dispatch_tool(
        "world_gen",
        {"template_family": "latent_preference", "num_nodes": 6, "edge_strength": 0.7, "seed": 42},
        result,
    )
    orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": result.world.id,
            "scenario_title": "Crop Yield Research",
            "scenario_description": "A research scenario about crop yields.",
            "domain": "agriculture",
            "node_renames": _full_renames(),
            "node_descriptions": {},
        },
        result,
    )
    return result.world.id


def test_dispatch_design_case_basic():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Crop Yield Investigation",
            "research_context": "A team is investigating factors affecting crop yield on planet XR-7.",
            "questions": [
                {
                    "question_text": "What is the most likely crop yield level?",
                    "eval_type": "infer_target",
                    "target_node": "crop_yield",
                    "rationale": "Primary research question",
                },
            ],
            "shared_budget": 4,
            "rationale": "Focus on inference",
        },
        result,
    )

    assert "error" not in output
    assert output["title"] == "Crop Yield Investigation"
    assert output["num_questions"] == 1
    assert output["tasks_generated"] == 1
    assert output["shared_budget"] == 4


def test_dispatch_design_case_multiple_questions():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Full Crop Analysis",
            "research_context": "Comprehensive analysis of crop yield factors on planet XR-7.",
            "questions": [
                {
                    "question_text": "What is the most likely crop yield?",
                    "eval_type": "infer_target",
                    "target_node": "crop_yield",
                },
                {
                    "question_text": "What measurement would tell us the most?",
                    "eval_type": "next_best_observation",
                    "target_node": "crop_yield",
                },
                {
                    "question_text": "Which hypothesis matches the observations?",
                    "eval_type": "hypothesis_selection",
                    "target_node": "crop_yield",
                },
            ],
            "shared_budget": 5,
        },
        result,
    )

    assert "error" not in output
    assert output["num_questions"] == 3
    assert output["tasks_generated"] == 3
    assert len(output["eval_types"]) == 3


def test_dispatch_design_case_stores_plan():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Stored Plan Test",
            "research_context": "Testing that the plan is stored for later use.",
            "questions": [
                {
                    "question_text": "What is the crop yield?",
                    "eval_type": "infer_target",
                    "target_node": "crop_yield",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert world_id in orch._case_plans
    plan = orch._case_plans[world_id]
    assert plan.title == "Stored Plan Test"
    assert len(plan.questions) == 1


def test_dispatch_design_case_invalid_target_node():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Invalid Target Test",
            "research_context": "Testing with a node that does not exist in the world.",
            "questions": [
                {
                    "question_text": "What is the nonexistent variable?",
                    "eval_type": "infer_target",
                    "target_node": "nonexistent_node",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "nonexistent_node" in output["error"]


def test_dispatch_design_case_empty_questions():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Empty Questions",
            "research_context": "No questions provided.",
            "questions": [],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output


def test_dispatch_design_case_unknown_world():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": "nonexistent",
            "title": "Ghost World",
            "research_context": "A world that does not exist.",
            "questions": [
                {
                    "question_text": "What is the outcome?",
                    "eval_type": "infer_target",
                    "target_node": "x",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "not found" in output["error"]


def test_dispatch_design_case_tasks_have_custom_questions():
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    custom_q = "Based on the soil samples, what crop yield level is most probable?"
    orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Custom Question Test",
            "research_context": "Verifying that generated tasks use custom question text.",
            "questions": [
                {
                    "question_text": custom_q,
                    "eval_type": "infer_target",
                    "target_node": "crop_yield",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    # result.task is a list of Task objects from generate_from_plan
    tasks = result.task
    assert len(tasks) == 1
    assert tasks[0].question == custom_q


# ---------- design_case: node hints validation ----------


def test_design_case_causal_effect_requires_intervention_node():
    """causal_effect without intervention_node should return error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Missing Hints",
            "research_context": "Test that hints are required for causal_effect.",
            "questions": [
                {
                    "question_text": "What is the effect of water pH on crop yield?",
                    "eval_type": "causal_effect",
                    "target_node": "crop_yield",
                    # NO intervention_node
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "intervention_node" in output["error"]


def test_design_case_causal_effect_with_hints_succeeds():
    """causal_effect with intervention_node should work and honor hints."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    custom_q = "What happens to crop yield if we change the water pH level?"
    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Causal Effect With Hints",
            "research_context": "Test that causal_effect hints flow to task generator.",
            "questions": [
                {
                    "question_text": custom_q,
                    "eval_type": "causal_effect",
                    "target_node": "crop_yield",
                    "intervention_node": "water_ph",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" not in output
    assert output["tasks_generated"] == 1
    # The task should use the hinted node and override question text
    tasks = result.task
    assert len(tasks) == 1
    task = tasks[0]
    # Intervention should be on water_ph (the hinted node)
    assert "water_ph" in task.intervention
    # Question text should be overridden since hints were honored
    assert task.question == custom_q


def test_design_case_best_intervention_requires_desired_state():
    """best_intervention without desired_state should return error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Missing Desired State",
            "research_context": "Test required hints for best_intervention.",
            "questions": [
                {
                    "question_text": "Which intervention maximizes high crop yield?",
                    "eval_type": "best_intervention",
                    "target_node": "crop_yield",
                    # NO desired_state
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "desired_state" in output["error"]


def test_design_case_best_intervention_with_hints_succeeds():
    """best_intervention with desired_state should work."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Best Intervention With Hints",
            "research_context": "Test that desired_state flows to task generator.",
            "questions": [
                {
                    "question_text": "Which intervention maximizes high crop yield?",
                    "eval_type": "best_intervention",
                    "target_node": "crop_yield",
                    "desired_state": "high",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" not in output
    assert output["tasks_generated"] == 1


def test_design_case_compare_interventions_requires_hints():
    """compare_interventions without compare_nodes + desired_state errors."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Missing Compare Hints",
            "research_context": "Test required hints for compare_interventions.",
            "questions": [
                {
                    "question_text": "Is water pH or nitrogen level more impactful?",
                    "eval_type": "compare_interventions",
                    "target_node": "crop_yield",
                    # NO compare_nodes, NO desired_state
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "compare_nodes" in output["error"] or "desired_state" in output["error"]


def test_design_case_compare_interventions_with_hints_succeeds():
    """compare_interventions with all required hints works."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Compare Interventions With Hints",
            "research_context": "Test that compare hints flow through.",
            "questions": [
                {
                    "question_text": "Is water pH or nitrogen level more impactful on yield?",
                    "eval_type": "compare_interventions",
                    "target_node": "crop_yield",
                    "compare_nodes": ["water_ph", "nitrogen_level"],
                    "desired_state": "high",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" not in output
    assert output["tasks_generated"] == 1


def test_design_case_should_condition_requires_both_hints():
    """should_condition needs intervention_node AND condition_variable."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    # Only intervention_node, missing condition_variable
    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Missing Condition Variable",
            "research_context": "Test required hints for should_condition.",
            "questions": [
                {
                    "question_text": "Should we control for root depth?",
                    "eval_type": "should_condition",
                    "target_node": "crop_yield",
                    "intervention_node": "water_ph",
                    # NO condition_variable
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "condition_variable" in output["error"]


def test_design_case_adjustment_set_requires_intervention_node():
    """adjustment_set without intervention_node should error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Missing Adjustment Hint",
            "research_context": "Test required hints for adjustment_set.",
            "questions": [
                {
                    "question_text": "What should we control for?",
                    "eval_type": "adjustment_set",
                    "target_node": "crop_yield",
                    # NO intervention_node
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "intervention_node" in output["error"]


def test_design_case_hint_invalid_node_name():
    """Hint with nonexistent node name should error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Bad Node Hint",
            "research_context": "Test that invalid node names in hints are caught.",
            "questions": [
                {
                    "question_text": "Effect of imaginary variable on yield?",
                    "eval_type": "causal_effect",
                    "target_node": "crop_yield",
                    "intervention_node": "nonexistent_node",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "nonexistent_node" in output["error"]


def test_design_case_safe_types_still_work_without_hints():
    """Safe types (infer_target, NBO, hypothesis_selection) need no hints."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Safe Types Only",
            "research_context": "Verify safe types work without any node hints.",
            "questions": [
                {
                    "question_text": "What is the most likely crop yield?",
                    "eval_type": "infer_target",
                    "target_node": "crop_yield",
                },
                {
                    "question_text": "What should we measure next?",
                    "eval_type": "next_best_observation",
                    "target_node": "crop_yield",
                },
                {
                    "question_text": "Which hypothesis best fits?",
                    "eval_type": "hypothesis_selection",
                    "target_node": "crop_yield",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" not in output
    assert output["tasks_generated"] == 3


def test_design_case_hint_invalid_desired_state():
    """desired_state that doesn't exist in target node's states should error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Bad Desired State",
            "research_context": "Test that invalid desired_state is caught.",
            "questions": [
                {
                    "question_text": "Which intervention maximizes FAKE crop yield?",
                    "eval_type": "best_intervention",
                    "target_node": "crop_yield",
                    "desired_state": "nonexistent_state",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "nonexistent_state" in output["error"]
    assert "desired_state" in output["error"]


def test_design_case_hint_target_node_rejected_as_intervention():
    """Target node used as intervention_node should error (not observable)."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Target As Intervention",
            "research_context": "Test that target node cannot be used as intervention.",
            "questions": [
                {
                    "question_text": "What if we intervene on crop yield itself?",
                    "eval_type": "causal_effect",
                    "target_node": "crop_yield",
                    "intervention_node": "crop_yield",
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "observable" in output["error"].lower()


def test_design_case_hint_latent_node_rejected_as_intervention():
    """Latent node used as intervention_node should error."""
    orch = Orchestrator(client=MagicMock())
    result = OrchestratorResult()
    world_id = _setup_world_with_semantics(orch, result)

    output = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Latent As Intervention",
            "research_context": "Test that latent node cannot be used as intervention.",
            "questions": [
                {
                    "question_text": "What if we intervene on the hidden cause?",
                    "eval_type": "causal_effect",
                    "target_node": "crop_yield",
                    "intervention_node": "soil_acidity",  # latent node
                },
            ],
            "shared_budget": 4,
        },
        result,
    )

    assert "error" in output
    assert "observable" in output["error"].lower()
