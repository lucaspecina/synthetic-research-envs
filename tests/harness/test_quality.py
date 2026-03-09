"""Tests for QualitySuite: layers A, B, C."""

from __future__ import annotations

import pytest

from sreg.harness.quality import (
    GeneratorDiversityMetrics,
    QualitySuiteReport,
    TaskQualityMetrics,
    WorldQualityMetrics,
    WorldReport,
    compute_generator_diversity,
    compute_task_quality,
    compute_world_quality,
    print_quality_report,
    run_quality_suite,
)
from sreg.models.world import NodeType
from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenConfig, WorldGenTool
from sreg.world.dag_generators import (
    generate_erdos_renyi,
    generate_spanning_tree,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world_gen():
    return WorldGenTool()


@pytest.fixture
def simple_world(world_gen):
    """A basic latent_preference world for testing."""
    config = WorldGenConfig(
        template_family="latent_preference", seed=42, num_nodes=6, edge_strength=0.7,
    )
    return world_gen.generate(config)


@pytest.fixture
def custom_world(world_gen):
    """A custom world from DAG generator."""
    spec = generate_spanning_tree(num_nodes=8, seed=42)
    config = CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=42)
    return world_gen.generate_custom(config)


@pytest.fixture
def batch_worlds(world_gen):
    """Multiple worlds for diversity testing."""
    worlds = []
    for seed in [1, 7, 42, 99, 123]:
        spec = generate_erdos_renyi(num_nodes=8, seed=seed, edge_prob=0.3)
        config = CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=seed)
        worlds.append(world_gen.generate_custom(config))
    return worlds


# ---------------------------------------------------------------------------
# Layer A: World Quality
# ---------------------------------------------------------------------------


class TestWorldQuality:
    def test_returns_correct_type(self, simple_world):
        result = compute_world_quality(simple_world)
        assert isinstance(result, WorldQualityMetrics)

    def test_worldcheck_pass(self, simple_world):
        result = compute_world_quality(simple_world)
        assert result.worldcheck_pass is True

    def test_node_edge_counts(self, simple_world):
        result = compute_world_quality(simple_world)
        assert result.num_nodes == len(simple_world.nodes)
        assert result.num_edges == len(simple_world.edges)

    def test_density_range(self, simple_world):
        result = compute_world_quality(simple_world)
        assert 0.0 <= result.density <= 1.0

    def test_treewidth_nonnegative(self, simple_world):
        result = compute_world_quality(simple_world)
        assert result.treewidth >= 0

    def test_graph_depth_positive(self, simple_world):
        result = compute_world_quality(simple_world)
        assert result.graph_depth >= 1

    def test_fan_in_within_limits(self, simple_world):
        result = compute_world_quality(simple_world)
        assert result.max_fan_in <= 4  # MAX_PARENTS

    def test_target_reachable_frac(self, simple_world):
        result = compute_world_quality(simple_world)
        # In latent_preference, all observables connect to target
        assert result.target_reachable_frac > 0.0

    def test_target_entropy_positive(self, simple_world):
        result = compute_world_quality(simple_world)
        assert result.target_entropy > 0.0

    def test_custom_world(self, custom_world):
        result = compute_world_quality(custom_world)
        assert isinstance(result, WorldQualityMetrics)
        assert result.num_nodes == 8

    def test_serializable(self, simple_world):
        result = compute_world_quality(simple_world)
        data = result.model_dump()
        assert isinstance(data, dict)
        assert "worldcheck_pass" in data
        reconstructed = WorldQualityMetrics(**data)
        assert reconstructed == result


# ---------------------------------------------------------------------------
# Layer B: Task Quality
# ---------------------------------------------------------------------------


class TestTaskQuality:
    def test_returns_correct_type(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert isinstance(result, TaskQualityMetrics)

    def test_teacher_beats_prior(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        # Teacher should improve over prior for a well-structured world
        assert result.teacher_kl <= result.prior_kl

    def test_teacher_beats_random(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert result.teacher_beats_random is True

    def test_kl_values_nonnegative(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert result.prior_kl >= 0.0
        assert result.teacher_kl >= 0.0
        assert result.random_kl >= 0.0

    def test_best_ig_nonnegative(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert result.best_ig >= 0.0

    def test_ig_gap_nonnegative(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert result.ig_gap >= 0.0

    def test_steps_to_stable_within_budget(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        obs_count = sum(1 for n in simple_world.nodes if n.type == NodeType.OBSERVABLE)
        budget = min(obs_count, 5)
        assert 0 <= result.teacher_steps_to_stable <= budget

    def test_nbo_field_is_bool(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert isinstance(result.nbo_nontrivial, bool)

    def test_hyp_field_is_bool(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert isinstance(result.hyp_distinguishable, bool)

    def test_useful_bundle_field(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        assert isinstance(result.useful_bundle, bool)

    def test_different_seeds_may_vary(self, simple_world):
        r1 = compute_task_quality(simple_world, seed=1)
        r2 = compute_task_quality(simple_world, seed=99)
        # At least some metrics should differ with different seeds
        assert r1.prior_kl != r2.prior_kl or r1.teacher_kl != r2.teacher_kl

    def test_serializable(self, simple_world):
        result = compute_task_quality(simple_world, seed=42)
        data = result.model_dump()
        assert isinstance(data, dict)
        reconstructed = TaskQualityMetrics(**data)
        assert reconstructed == result


# ---------------------------------------------------------------------------
# Layer C: Generator Diversity
# ---------------------------------------------------------------------------


class TestGeneratorDiversity:
    def test_returns_correct_type(self, batch_worlds):
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
                task_quality=compute_task_quality(w, seed=w.seed),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        assert isinstance(result, GeneratorDiversityMetrics)

    def test_count_matches(self, batch_worlds):
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        assert result.count == len(batch_worlds)

    def test_acceptance_rate_range(self, batch_worlds):
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        assert 0.0 <= result.acceptance_rate <= 1.0

    def test_empty_batch(self):
        result = compute_generator_diversity([])
        assert result.count == 0
        assert result.acceptance_rate == 0.0

    def test_fan_distributions_populated(self, batch_worlds):
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        assert len(result.fan_in_distribution) > 0
        assert len(result.fan_out_distribution) > 0

    def test_with_task_quality(self, batch_worlds):
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
                task_quality=compute_task_quality(w, seed=w.seed),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        assert result.useful_bundle_rate >= 0.0
        assert result.ig_gap_std >= 0.0

    def test_serializable(self, batch_worlds):
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        data = result.model_dump()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


class TestRunQualitySuite:
    def test_returns_full_report(self, simple_world):
        report = run_quality_suite([simple_world])
        assert isinstance(report, QualitySuiteReport)
        assert len(report.worlds) == 1
        assert report.diversity is not None
        assert report.summary is not None

    def test_multiple_worlds(self, batch_worlds):
        report = run_quality_suite(batch_worlds)
        assert len(report.worlds) == len(batch_worlds)

    def test_summary_has_rates(self, simple_world):
        report = run_quality_suite([simple_world])
        assert "worldcheck_pass_rate" in report.summary
        assert "teacher_beats_prior_rate" in report.summary

    def test_skips_task_quality_on_failed_worldcheck(self, world_gen):
        """If WorldCheck fails, task quality is skipped gracefully."""
        # Create a minimal world that might fail WorldCheck
        spec = generate_erdos_renyi(num_nodes=5, seed=42, edge_prob=0.1)
        config = CustomWorldGenConfig(dag_spec=spec, edge_strength=0.3, seed=42)
        world = world_gen.generate_custom(config)
        # Even if it fails or passes, the suite should handle it
        report = run_quality_suite([world])
        assert len(report.worlds) == 1

    def test_custom_seeds(self, simple_world):
        report = run_quality_suite([simple_world], seeds=[123])
        assert report.worlds[0].seed == 123


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------


class TestPrintReport:
    def test_prints_without_error(self, simple_world):
        report = run_quality_suite([simple_world])
        text = print_quality_report(report)
        assert "QUALITY SUITE REPORT" in text
        assert "SUMMARY" in text

    def test_contains_world_info(self, simple_world):
        report = run_quality_suite([simple_world])
        text = print_quality_report(report)
        assert "PASS" in text or "FAIL" in text

    def test_batch_report(self, batch_worlds):
        report = run_quality_suite(batch_worlds)
        text = print_quality_report(report)
        assert "GENERATOR DIVERSITY" in text


# ---------------------------------------------------------------------------
# Cross-template tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template", ["latent_preference", "causal_chain", "fork_collider"])
def test_quality_suite_per_template(world_gen, template):
    """Each template family should produce a valid quality report."""
    config = WorldGenConfig(
        template_family=template, seed=42, num_nodes=6, edge_strength=0.7,
    )
    world = world_gen.generate(config)
    report = run_quality_suite([world])
    assert len(report.worlds) == 1
    assert report.worlds[0].world_quality.worldcheck_pass is True
    assert report.worlds[0].task_quality is not None


@pytest.mark.parametrize("generator,kwargs", [
    ("erdos_renyi", {"num_nodes": 8, "edge_prob": 0.3}),
    ("spanning_tree", {"num_nodes": 8}),
    ("layered", {"num_layers": 3, "nodes_per_layer": 3}),
])
def test_quality_suite_per_generator(world_gen, generator, kwargs):
    """Each DAG generator should produce worlds that pass quality analysis."""
    from sreg.world import dag_generators

    gen_fn = getattr(dag_generators, f"generate_{generator}")
    spec = gen_fn(seed=42, **kwargs)
    config = CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=42)
    world = world_gen.generate_custom(config)

    wq = compute_world_quality(world)
    assert isinstance(wq, WorldQualityMetrics)
    # At minimum, should compute all metrics without errors
    assert wq.num_nodes > 0
    assert wq.target_entropy >= 0.0
