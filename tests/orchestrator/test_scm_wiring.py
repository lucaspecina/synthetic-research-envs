"""Tests for SCM orchestrator wiring -- handler dispatch, no LLM calls."""

from unittest.mock import MagicMock

from sreg.orchestrator.orchestrator import Orchestrator, OrchestratorResult
from sreg.orchestrator.prompts import TOOL_DEFINITIONS
from sreg.world.scm import SCMWorld

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orch() -> Orchestrator:
    return Orchestrator(client=MagicMock())


def _epi_spec_args(seed: int = 42) -> dict:
    """Epidemiology SCM spec: pollution -> exposure -> disease, with confounder."""
    return {
        "variables": [
            {
                "name": "socioeconomic_status",
                "role": "observable",
                "unit": "index (0-100)",
                "range": [0, 100],
                "description": "Composite socioeconomic index",
                "equation": "normal(50, 15)",
            },
            {
                "name": "pollution_source",
                "role": "latent",
                "unit": "tons/year",
                "range": [0, 500],
                "description": "Industrial emissions near residential area",
                "equation": "uniform(50, 400)",
            },
            {
                "name": "air_quality",
                "role": "observable",
                "unit": "AQI",
                "range": [0, 300],
                "description": "Air quality index at monitoring stations",
                "equation": (
                    "0.4 * pollution_source "
                    "- 0.1 * socioeconomic_status "
                    "+ normal(80, 10)"
                ),
            },
            {
                "name": "outdoor_activity",
                "role": "observable",
                "unit": "hours/week",
                "range": [0, 40],
                "description": "Hours of outdoor physical activity per week",
                "equation": (
                    "max(0, 15 - 0.03 * air_quality "
                    "+ 0.05 * socioeconomic_status "
                    "+ normal(0, 3))"
                ),
            },
            {
                "name": "healthcare_access",
                "role": "observable",
                "unit": "score (0-10)",
                "range": [0, 10],
                "description": "Healthcare accessibility score",
                "equation": (
                    "min(10, max(0, 0.08 * socioeconomic_status "
                    "+ normal(2, 1)))"
                ),
            },
            {
                "name": "respiratory_disease",
                "role": "target",
                "unit": "severity (0-100)",
                "range": [0, 100],
                "description": "Respiratory disease severity index",
                "equation": (
                    "max(0, 0.3 * air_quality "
                    "- 0.5 * outdoor_activity "
                    "- 1.5 * healthcare_access "
                    "+ normal(10, 5))"
                ),
            },
        ],
        "edges": [
            {"from": "socioeconomic_status", "to": "air_quality"},
            {"from": "socioeconomic_status", "to": "outdoor_activity"},
            {"from": "socioeconomic_status", "to": "healthcare_access"},
            {"from": "pollution_source", "to": "air_quality"},
            {"from": "air_quality", "to": "outdoor_activity"},
            {"from": "air_quality", "to": "respiratory_disease"},
            {"from": "outdoor_activity", "to": "respiratory_disease"},
            {"from": "healthcare_access", "to": "respiratory_disease"},
        ],
        "seed": seed,
    }


def _minimal_spec_args(seed: int = 42) -> dict:
    """Minimal 3-variable SCM for quick tests."""
    return {
        "variables": [
            {
                "name": "X",
                "role": "observable",
                "unit": "units",
                "equation": "normal(10, 2)",
            },
            {
                "name": "Z",
                "role": "latent",
                "unit": "units",
                "equation": "uniform(0, 5)",
            },
            {
                "name": "Y",
                "role": "target",
                "unit": "units",
                "equation": "0.5 * X + 0.3 * Z + normal(0, 1)",
            },
        ],
        "edges": [
            {"from": "X", "to": "Y"},
            {"from": "Z", "to": "Y"},
        ],
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def test_scm_construct_in_tool_definitions():
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "scm_construct" in names


def test_scm_construct_tool_has_required_fields():
    tool = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == "scm_construct")
    fn = tool["function"]
    assert "description" in fn
    assert "parameters" in fn
    required = fn["parameters"]["required"]
    assert "variables" in required
    assert "edges" in required
    assert "seed" in required


# ---------------------------------------------------------------------------
# scm_construct handler
# ---------------------------------------------------------------------------


def test_scm_construct_basic():
    orch = _make_orch()
    result = OrchestratorResult()
    output = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)

    assert "error" not in output
    assert "world_id" in output
    assert output["num_variables"] == 3
    assert output["num_edges"] == 2
    assert result.world is not None
    assert isinstance(result.world, SCMWorld)
    assert result.attempts == 1


def test_scm_construct_epidemiology():
    orch = _make_orch()
    result = OrchestratorResult()
    output = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)

    assert "error" not in output
    assert output["num_variables"] == 6
    assert output["num_edges"] == 8

    # Check variable roles in response
    roles = {v["name"]: v["role"] for v in output["variables"]}
    assert roles["pollution_source"] == "latent"
    # target role removed: OI uses SQ roles instead. All non-latent are observable.
    assert roles["respiratory_disease"] == "observable"
    assert roles["air_quality"] == "observable"


def test_scm_construct_invalid_equation():
    orch = _make_orch()
    result = OrchestratorResult()
    args = _minimal_spec_args()
    args["variables"][2]["equation"] = "import os"
    output = orch._dispatch_tool("scm_construct", args, result)

    assert "error" in output
    assert result.world is None


def test_scm_construct_cycle():
    orch = _make_orch()
    result = OrchestratorResult()
    args = _minimal_spec_args()
    args["edges"].append({"from": "Y", "to": "X"})  # creates cycle
    output = orch._dispatch_tool("scm_construct", args, result)

    assert "error" in output


def test_scm_construct_empty_variables():
    orch = _make_orch()
    result = OrchestratorResult()
    output = orch._dispatch_tool("scm_construct", {"variables": [], "edges": []}, result)

    assert "error" in output


def test_scm_construct_stores_seed():
    orch = _make_orch()
    result = OrchestratorResult()
    output = orch._dispatch_tool("scm_construct", _minimal_spec_args(seed=99), result)

    world_id = output["world_id"]
    assert orch._world_seeds[world_id] == 99


# ---------------------------------------------------------------------------
# world_check with SCMWorld
# ---------------------------------------------------------------------------


def test_world_check_scm_auto_pass():
    orch = _make_orch()
    result = OrchestratorResult()

    # First create the world
    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    # Then check it
    check_out = orch._dispatch_tool("world_check", {"world_id": world_id}, result)

    assert check_out["passed"] is True
    assert check_out["failures"] == []
    assert result.validation_passed is True


def test_world_check_unknown_world():
    orch = _make_orch()
    result = OrchestratorResult()
    output = orch._dispatch_tool("world_check", {"world_id": "nonexistent"}, result)

    assert "error" in output


# ---------------------------------------------------------------------------
# apply_semantics with SCMWorld
# ---------------------------------------------------------------------------


def test_apply_semantics_scm_stores_metadata():
    orch = _make_orch()
    result = OrchestratorResult()

    # Create world
    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    # Apply semantics
    sem_out = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Air pollution and respiratory health in Newara district",
            "scenario_description": "Researchers investigate the relationship...",
            "domain": "environmental epidemiology",
            "node_renames": {},  # empty is fine for SCM
            "node_descriptions": {},
        },
        result,
    )

    assert "error" not in sem_out
    assert sem_out["scenario_title"] == "Air pollution and respiratory health in Newara district"
    assert sem_out["domain"] == "environmental epidemiology"

    # Check metadata stored
    assert world_id in orch._world_semantics
    assert orch._world_semantics[world_id]["domain"] == "environmental epidemiology"


def test_apply_semantics_scm_variables_listed():
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    sem_out = orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Test",
            "scenario_description": "Test",
            "domain": "test",
            "node_renames": {},
            "node_descriptions": {},
        },
        result,
    )

    var_names = {v["name"] for v in sem_out["variables"]}
    assert "X" in var_names
    assert "Y" in var_names

    # Latent variable marked correctly
    roles = {v["name"]: v["role"] for v in sem_out["variables"]}
    assert roles["Z"] == "latent"


# ---------------------------------------------------------------------------
# design_case with SCMWorld
# ---------------------------------------------------------------------------


def test_design_case_scm_basic():
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    case_out = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Air pollution health impact",
            "research_context": "Investigating respiratory disease drivers",
            "research_brief": (
                "Investigate the relationship between environmental pollution "
                "and respiratory health outcomes in this community."
            ),
            "deliverables": ["Identify causal drivers", "Recommend interventions"],
            "questions": [
                {
                    "question_text": (
                        "What is the causal effect of air quality on respiratory disease?"
                    ),
                    "eval_type": "causal_effect",
                    "target_node": "respiratory_disease",
                    "intervention_node": "air_quality",
                },
                {
                    "question_text": (
                        "Based on the data, what is the likely severity "
                        "of respiratory disease?"
                    ),
                    "eval_type": "infer_target",
                    "target_node": "respiratory_disease",
                },
            ],
            "shared_budget": 5,
        },
        result,
    )

    assert "error" not in case_out
    assert case_out["num_questions"] == 2
    assert case_out["tasks_generated"] == 2


def test_design_case_scm_validates_node_names():
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    case_out = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Test case title",
            "research_context": "Testing node name validation in SCM.",
            "research_brief": "Investigate the causal system.",
            "questions": [
                {
                    "question_text": "What about nonexistent_var?",
                    "eval_type": "infer_target",
                    "target_node": "nonexistent_var",
                },
            ],
            "shared_budget": 3,
        },
        result,
    )

    assert "error" in case_out
    assert "nonexistent_var" in case_out["error"]


def test_design_case_scm_validates_observable_hints():
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    # Z is latent, should not be accepted as intervention_node
    case_out = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Test case title",
            "research_context": "Testing observable hint validation in SCM.",
            "research_brief": "Investigate the causal system.",
            "questions": [
                {
                    "question_text": "Effect of Z?",
                    "eval_type": "causal_effect",
                    "target_node": "Y",
                    "intervention_node": "Z",
                },
            ],
            "shared_budget": 3,
        },
        result,
    )

    assert "error" in case_out
    assert "observable" in case_out["error"].lower()


def test_design_case_scm_skips_desired_state_validation():
    """SCM has no discrete states, so desired_state should not be validated."""
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    # In BN, desired_state must match a discrete state. In SCM, any string is OK.
    case_out = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Test case title",
            "research_context": "Testing desired state validation skip for SCM.",
            "research_brief": "Investigate which intervention maximizes health.",
            "questions": [
                {
                    "question_text": "Which intervention maximizes health?",
                    "eval_type": "best_intervention",
                    "target_node": "respiratory_disease",
                    "desired_state": "minimize",
                },
            ],
            "shared_budget": 5,
        },
        result,
    )

    # Should not fail on desired_state validation
    assert "desired_state" not in case_out.get("error", "")


# ---------------------------------------------------------------------------
# build_problem with SCMWorld
# ---------------------------------------------------------------------------


def test_build_problem_scm_basic():
    orch = _make_orch()
    result = OrchestratorResult()

    # Create world
    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    # Apply semantics
    orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Respiratory health in Newara",
            "scenario_description": "A study on pollution and health",
            "domain": "epidemiology",
            "node_renames": {},
            "node_descriptions": {},
        },
        result,
    )

    # Build problem
    prob_out = orch._dispatch_tool(
        "build_problem",
        {
            "world_id": world_id,
            "budget": 5,
            "data_format": "tabular",
            "num_data_rows": 200,
        },
        result,
    )

    assert "error" not in prob_out
    assert result.problem is not None
    assert result.problem.title == "Respiratory health in Newara"
    assert result.problem.domain == "epidemiology"
    assert len(result.problem.data_assets) > 0
    assert result.problem.budget == 5


def test_build_problem_scm_without_semantics():
    """build_problem should work even without apply_semantics."""
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    prob_out = orch._dispatch_tool(
        "build_problem",
        {
            "world_id": world_id,
            "budget": 3,
            "data_format": "tabular",
        },
        result,
    )

    assert "error" not in prob_out
    assert result.problem is not None
    # Should use defaults when no semantics stored
    assert result.problem.domain == "continuous_scm"


def test_build_problem_scm_with_case_plan():
    """Full pipeline: scm_construct -> apply_semantics -> design_case -> build_problem."""
    orch = _make_orch()
    result = OrchestratorResult()

    # 1. Create world
    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    # 2. Apply semantics
    orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Respiratory health in Newara",
            "scenario_description": "Pollution study",
            "domain": "epidemiology",
            "node_renames": {},
            "node_descriptions": {},
        },
        result,
    )

    # 3. Design case
    orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Pollution impact on health",
            "research_context": "Understanding respiratory disease drivers",
            "research_brief": (
                "Investigate the relationship between environmental pollution "
                "and respiratory health in the Newara district."
            ),
            "deliverables": ["Identify drivers", "Recommend actions"],
            "questions": [
                {
                    "question_text": "Effect of air quality on disease?",
                    "eval_type": "causal_effect",
                    "target_node": "respiratory_disease",
                    "intervention_node": "air_quality",
                },
                {
                    "question_text": "What is the likely severity?",
                    "eval_type": "infer_target",
                    "target_node": "respiratory_disease",
                },
            ],
            "shared_budget": 5,
        },
        result,
    )

    # 4. Build problem
    prob_out = orch._dispatch_tool(
        "build_problem",
        {
            "world_id": world_id,
            "budget": 5,
            "data_format": "tabular",
            "num_data_rows": 200,
        },
        result,
    )

    assert "error" not in prob_out
    assert result.problem is not None
    assert result.problem.title == "Respiratory health in Newara"
    assert len(result.problem.data_assets) > 0


# ---------------------------------------------------------------------------
# E2E pipeline validation
# ---------------------------------------------------------------------------


def test_build_problem_scm_uses_research_brief():
    """When CasePlan has research_brief, it becomes the visible research question."""
    orch = _make_orch()
    result = OrchestratorResult()

    # 1. Create world
    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    # 2. Apply semantics
    orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Respiratory health in Newara",
            "scenario_description": "Pollution study",
            "domain": "epidemiology",
            "node_renames": {},
            "node_descriptions": {},
        },
        result,
    )

    # 3. Design case WITH research_brief
    design_out = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Pollution impact on health",
            "research_context": "Understanding respiratory disease drivers",
            "research_brief": (
                "Investigate the relationship between environmental pollution "
                "and respiratory health outcomes in the Newara district. "
                "Determine which factors are most important and whether "
                "interventions could reduce disease burden."
            ),
            "deliverables": [
                "Identify primary environmental drivers of respiratory disease",
                "Evaluate potential intervention strategies",
                "Recommend monitoring priorities",
            ],
            "questions": [
                {
                    "question_text": "Effect of air quality on disease?",
                    "eval_type": "causal_effect",
                    "target_node": "respiratory_disease",
                    "intervention_node": "air_quality",
                },
            ],
            "shared_budget": 5,
        },
        result,
    )
    assert "error" not in design_out

    # 4. Build problem
    prob_out = orch._dispatch_tool(
        "build_problem",
        {
            "world_id": world_id,
            "budget": 5,
            "data_format": "tabular",
        },
        result,
    )

    assert "error" not in prob_out
    problem = result.problem
    assert problem is not None
    # Brief should be visible, not the eval question
    assert "environmental pollution" in problem.research_question
    assert "respiratory health" in problem.research_question
    # Deliverables should appear
    assert "environmental drivers" in problem.research_question
    assert "monitoring priorities" in problem.research_question
    # The eval question should NOT be the visible question
    assert "Effect of air quality on disease" not in problem.research_question


def test_design_case_stores_brief_in_plan():
    """Verify research_brief and deliverables are stored in CasePlan."""
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Simple test case",
            "research_context": "Testing brief storage in the plan.",
            "research_brief": "Investigate the causal chain from X to Y.",
            "deliverables": ["Identify drivers", "Recommend actions"],
            "questions": [
                {
                    "question_text": "What is the distribution of Y?",
                    "eval_type": "infer_target",
                    "target_node": "Y",
                },
            ],
            "shared_budget": 3,
        },
        result,
    )

    plan = orch._case_plans.get(world_id)
    assert plan is not None
    assert plan.research_brief == "Investigate the causal chain from X to Y."
    assert plan.deliverables == ["Identify drivers", "Recommend actions"]


def test_design_case_scm_rejects_empty_brief():
    """SCM worlds require a non-empty research_brief."""
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _minimal_spec_args(), result)
    world_id = create_out["world_id"]

    # No research_brief
    out = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Test case",
            "research_context": "Testing empty brief rejection.",
            "questions": [
                {
                    "question_text": "What is the distribution of Y?",
                    "eval_type": "infer_target",
                    "target_node": "Y",
                },
            ],
            "shared_budget": 3,
        },
        result,
    )
    assert "error" in out
    assert "research_brief" in out["error"]

    # Empty string brief
    out2 = orch._dispatch_tool(
        "design_case",
        {
            "world_id": world_id,
            "title": "Test case",
            "research_context": "Testing empty brief rejection.",
            "research_brief": "   ",
            "questions": [
                {
                    "question_text": "What is the distribution of Y?",
                    "eval_type": "infer_target",
                    "target_node": "Y",
                },
            ],
            "shared_budget": 3,
        },
        result,
    )
    assert "error" in out2


def test_e2e_scm_pipeline_data_quality():
    """Verify sampled data makes sense: no latent columns, reasonable values."""
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    orch._dispatch_tool(
        "apply_semantics",
        {
            "world_id": world_id,
            "scenario_title": "Test",
            "scenario_description": "Test",
            "domain": "test",
            "node_renames": {},
            "node_descriptions": {},
        },
        result,
    )

    orch._dispatch_tool(
        "build_problem",
        {
            "world_id": world_id,
            "budget": 5,
            "data_format": "tabular",
            "num_data_rows": 200,
        },
        result,
    )

    problem = result.problem
    assert problem is not None

    # Data should not contain latent variable
    for asset in problem.data_assets:
        col_names = asset.columns
        assert "pollution_source" not in col_names, "Latent variable leaked into data"

    # Should have observable variables
    all_cols = set()
    for asset in problem.data_assets:
        all_cols.update(asset.columns)
    assert "air_quality" in all_cols
    assert "respiratory_disease" in all_cols


def test_e2e_scm_pipeline_actions():
    """Verify available actions are based on observable variables."""
    orch = _make_orch()
    result = OrchestratorResult()

    create_out = orch._dispatch_tool("scm_construct", _epi_spec_args(), result)
    world_id = create_out["world_id"]

    orch._dispatch_tool(
        "build_problem",
        {
            "world_id": world_id,
            "budget": 5,
            "data_format": "tabular",
        },
        result,
    )

    problem = result.problem
    assert problem is not None

    action_nodes = {a.node for a in problem.available_actions}
    # Latent variable should not have an action
    assert "pollution_source" not in action_nodes
    # Observable variables (minus target) should have actions
    assert "air_quality" in action_nodes
