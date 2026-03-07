"""Tests for world validation tool."""

import pytest

from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


@pytest.fixture
def gen():
    return WorldGenTool()


@pytest.fixture
def checker():
    return WorldCheckTool()


def test_valid_world_passes(gen, checker):
    world = gen.generate(WorldGenConfig(seed=42))
    result = checker.check(world)

    assert result.passed, f"Failures: {result.failures}"
    assert result.metrics["dag_valid"] == 1.0
    assert result.metrics["num_latent"] >= 1.0
    assert result.metrics["prior_target_entropy"] > 0


def test_dag_validity_reported(gen, checker):
    world = gen.generate(WorldGenConfig(seed=0))
    result = checker.check(world)

    assert result.metrics["dag_valid"] == 1.0


def test_path_to_target_exists(gen, checker):
    world = gen.generate(WorldGenConfig(seed=0))
    result = checker.check(world)

    assert result.metrics["min_path_to_target"] >= 1.0


def test_d_separation_found(gen, checker):
    world = gen.generate(WorldGenConfig(seed=0, num_nodes=6))
    result = checker.check(world)

    assert result.metrics.get("has_d_separation", 0) == 1.0


def test_entropy_above_threshold(gen, checker):
    world = gen.generate(WorldGenConfig(seed=42))
    result = checker.check(world)

    assert result.metrics["prior_target_entropy"] >= 0.3


def test_all_100_worlds_pass(gen, checker):
    """All 100 generated worlds should pass validation."""
    for seed in range(100):
        world = gen.generate(WorldGenConfig(seed=seed))
        result = checker.check(world)
        assert result.passed, f"World seed={seed} failed: {result.failures}"


def test_different_edge_strengths_produce_different_entropy(gen, checker):
    """Worlds with different edge_strength should have measurably different entropy."""
    entropies = {}
    for strength in [0.3, 0.5, 0.7, 0.9]:
        # Average over several seeds to smooth out randomness
        total_entropy = 0.0
        n_seeds = 10
        for seed in range(n_seeds):
            config = WorldGenConfig(seed=seed, edge_strength=strength)
            world = gen.generate(config)
            result = checker.check(world)
            total_entropy += result.metrics["prior_target_entropy"]
        entropies[strength] = total_entropy / n_seeds

    # Prior entropy is about the marginal of the target, which is affected
    # by edge_strength through the CPD structure. We just verify we get
    # non-trivial, varying values.
    values = list(entropies.values())
    assert max(values) > min(values), f"Entropies don't vary: {entropies}"


def test_custom_thresholds():
    checker = WorldCheckTool(min_entropy=2.0)  # very strict
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(seed=42, num_states=3))
    result = checker.check(world)

    # With max log2(3) ≈ 1.58 bits, entropy can't exceed 2.0 for 3 states
    # So this should fail the entropy check
    entropy_failures = [f for f in result.failures if "entropy" in f.lower()]
    assert len(entropy_failures) > 0
