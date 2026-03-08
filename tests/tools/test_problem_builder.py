"""Tests for ProblemBuilder."""

from sreg.models.research_problem import ResearchProblem
from sreg.tools.data_sampler import DataSamplerConfig
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _make_world(**kwargs):
    defaults = {
        "template_family": "latent_preference",
        "num_nodes": 6,
        "edge_strength": 0.7,
        "seed": 42,
    }
    defaults.update(kwargs)
    config = WorldGenConfig(**defaults)
    return WorldGenTool().generate(config)


def test_build_basic():
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world, budget=4)

    assert isinstance(problem, ResearchProblem)
    assert problem.budget == 4
    assert problem.world_id == world.id
    assert len(problem.data_assets) > 0
    assert len(problem.available_actions) > 0
    assert problem.target_node == "target_outcome"
    assert len(problem.target_states) >= 2


def test_build_with_semantics():
    world = _make_world()
    world = world.model_copy(
        update={
            "scenario_title": "Marine Investigation",
            "scenario_description": "A study of ocean dynamics.",
            "domain": "oceanography",
            "theoretical_context": "Prior studies suggest...",
        }
    )

    builder = ProblemBuilder()
    problem = builder.build(world, budget=3)

    assert problem.title == "Marine Investigation"
    assert problem.description == "A study of ocean dynamics."
    assert problem.domain == "oceanography"
    assert problem.theoretical_context == "Prior studies suggest..."


def test_build_custom_data_config():
    world = _make_world()
    builder = ProblemBuilder()
    data_config = DataSamplerConfig(num_rows=20, format="both", seed=0)
    problem = builder.build(world, budget=5, data_config=data_config)

    assert len(problem.data_assets) == 2


def test_actions_are_observable_nodes():
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world)

    action_nodes = {a.node for a in problem.available_actions}
    observable_names = {n.name for n in world.nodes if n.type == "observable"}
    assert action_nodes == observable_names


def test_research_question_mentions_target():
    world = _make_world()
    builder = ProblemBuilder()
    problem = builder.build(world)

    assert "target_outcome" in problem.research_question
