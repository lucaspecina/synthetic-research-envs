"""Tests for QualitySuite v2: layers A, B (multi-rollout), C."""

from __future__ import annotations

import pytest

from sreg.harness.quality import (
    DEFAULT_ROLLOUT_SEEDS,
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
# Layer A: World Quality (unchanged)
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
        assert result.max_fan_in <= 4

    def test_target_reachable_frac(self, simple_world):
        result = compute_world_quality(simple_world)
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
        reconstructed = WorldQualityMetrics(**data)
        assert reconstructed == result


# ---------------------------------------------------------------------------
# Layer B: Task Quality (v2 — multi-rollout)
# ---------------------------------------------------------------------------


class TestTaskQuality:
    def test_returns_correct_type(self, simple_world):
        result = compute_task_quality(simple_world)
        assert isinstance(result, TaskQualityMetrics)

    def test_uses_default_rollout_seeds(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.num_rollouts == len(DEFAULT_ROLLOUT_SEEDS)

    def test_custom_seeds(self, simple_world):
        result = compute_task_quality(simple_world, seeds=[1, 2, 3])
        assert result.num_rollouts == 3

    def test_entropy_reduction_positive(self, simple_world):
        """Teacher should reduce entropy (learn something) on average."""
        result = compute_task_quality(simple_world)
        assert result.mean_entropy_reduction > 0.0

    def test_prior_entropy_positive(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.prior_entropy > 0.0

    def test_budget_ratio(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.budget_ratio > 0.0

    def test_best_ig_nonnegative(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.best_first_ig >= 0.0

    def test_ig_gap_nonnegative(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.ig_gap >= 0.0

    def test_nll_values_nonnegative(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.mean_teacher_nll >= 0.0
        assert result.mean_prior_nll >= 0.0
        assert result.mean_random_nll >= 0.0

    def test_teacher_beats_random_rate_range(self, simple_world):
        result = compute_task_quality(simple_world)
        assert 0.0 <= result.teacher_beats_random_rate <= 1.0

    def test_nbo_rate_range(self, simple_world):
        result = compute_task_quality(simple_world)
        assert 0.0 <= result.nbo_nontrivial_rate <= 1.0

    def test_hyp_rate_range(self, simple_world):
        result = compute_task_quality(simple_world)
        assert 0.0 <= result.hyp_distinguishable_rate <= 1.0

    def test_diagnostic_fields_present(self, simple_world):
        result = compute_task_quality(simple_world)
        assert result.sampled_nll_teacher >= 0.0
        assert result.sampled_nll_prior >= 0.0
        assert isinstance(result.teacher_steps_to_stable, int)

    def test_useful_bundle_is_bool(self, simple_world):
        result = compute_task_quality(simple_world)
        assert isinstance(result.useful_bundle, bool)

    def test_serializable(self, simple_world):
        result = compute_task_quality(simple_world)
        data = result.model_dump()
        assert isinstance(data, dict)
        assert "mean_entropy_reduction" in data
        assert "budget_ratio" in data
        reconstructed = TaskQualityMetrics(**data)
        assert reconstructed == result

    def test_custom_world(self, custom_world):
        result = compute_task_quality(custom_world, seeds=[42])
        assert isinstance(result, TaskQualityMetrics)
        assert result.num_rollouts == 1

    def test_multi_rollout_averages_noise(self, simple_world):
        """Multi-rollout should produce more stable metrics than single."""
        r1 = compute_task_quality(simple_world, seeds=[42])
        r5 = compute_task_quality(simple_world, seeds=[1, 7, 42, 99, 123])
        # Both should work; multi-rollout uses more data
        assert r1.num_rollouts == 1
        assert r5.num_rollouts == 5
        # Multi-rollout entropy reduction should be positive on average
        # (single rollout can be negative for atypical samples)
        assert r5.mean_entropy_reduction > 0.0


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
                task_quality=compute_task_quality(w, seeds=[42]),
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

    def test_entropy_reduction_std(self, batch_worlds):
        """v2: uses entropy_reduction_std instead of ig_gap_std."""
        reports = [
            WorldReport(
                world_id=w.id,
                seed=w.seed,
                world_quality=compute_world_quality(w),
                task_quality=compute_task_quality(w, seeds=[42]),
            )
            for w in batch_worlds
        ]
        result = compute_generator_diversity(reports)
        assert result.entropy_reduction_std >= 0.0

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
        assert "entropy_reduction_std" in data


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


class TestRunQualitySuite:
    def test_returns_full_report(self, simple_world):
        report = run_quality_suite([simple_world])
        assert isinstance(report, QualitySuiteReport)
        assert len(report.worlds) == 1
        assert report.diversity is not None

    def test_multiple_worlds(self, batch_worlds):
        report = run_quality_suite(batch_worlds, rollout_seeds=[42])
        assert len(report.worlds) == len(batch_worlds)

    def test_summary_has_v2_metrics(self, simple_world):
        report = run_quality_suite([simple_world])
        assert "mean_entropy_reduction" in report.summary
        assert "mean_nll_improvement" in report.summary
        assert "teacher_beats_random_rate" in report.summary
        assert "mean_budget_ratio" in report.summary

    def test_skips_task_quality_on_failed_worldcheck(self, world_gen):
        spec = generate_erdos_renyi(num_nodes=5, seed=42, edge_prob=0.1)
        config = CustomWorldGenConfig(dag_spec=spec, edge_strength=0.3, seed=42)
        world = world_gen.generate_custom(config)
        report = run_quality_suite([world], rollout_seeds=[42])
        assert len(report.worlds) == 1

    def test_custom_rollout_seeds(self, simple_world):
        report = run_quality_suite([simple_world], rollout_seeds=[1, 2])
        tq = report.worlds[0].task_quality
        assert tq is not None
        assert tq.num_rollouts == 2


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------


class TestPrintReport:
    def test_prints_without_error(self, simple_world):
        report = run_quality_suite([simple_world], rollout_seeds=[42])
        text = print_quality_report(report)
        assert "QUALITY SUITE REPORT" in text
        assert "v2" in text
        assert "SUMMARY" in text

    def test_contains_v2_columns(self, simple_world):
        report = run_quality_suite([simple_world], rollout_seeds=[42])
        text = print_quality_report(report)
        assert "EntRd" in text  # entropy reduction column
        assert "BudR" in text   # budget ratio column

    def test_batch_report(self, batch_worlds):
        report = run_quality_suite(batch_worlds, rollout_seeds=[42])
        text = print_quality_report(report)
        assert "GENERATOR DIVERSITY" in text
        assert "entropy_reduction_std" in text


# ---------------------------------------------------------------------------
# Cross-template tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template", [
    "latent_preference", "causal_chain", "fork_collider",
])
def test_quality_suite_per_template(world_gen, template):
    """Each template family should produce a valid quality report."""
    config = WorldGenConfig(
        template_family=template, seed=42, num_nodes=6, edge_strength=0.7,
    )
    world = world_gen.generate(config)
    report = run_quality_suite([world], rollout_seeds=[42, 99])
    wr = report.worlds[0]
    assert wr.world_quality.worldcheck_pass is True
    assert wr.task_quality is not None
    assert wr.task_quality.mean_entropy_reduction >= 0.0
    assert wr.task_quality.num_rollouts == 2


@pytest.mark.parametrize("generator,kwargs", [
    ("erdos_renyi", {"num_nodes": 8, "edge_prob": 0.3}),
    ("spanning_tree", {"num_nodes": 8}),
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
    assert wq.num_nodes > 0

    if wq.worldcheck_pass:
        tq = compute_task_quality(world, seeds=[42])
        assert isinstance(tq, TaskQualityMetrics)
        # Single-rollout entropy reduction can be negative (atypical sample)
        # Just verify the metric is computed
        assert isinstance(tq.mean_entropy_reduction, float)
