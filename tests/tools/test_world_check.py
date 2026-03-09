"""Tests for world validation tool."""

import pytest

from sreg.models.dag_spec import DAGNodeSpec, DAGSpec, MAX_PARENTS
from sreg.models.world import NodeType
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenConfig, WorldGenTool


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


# ---------------------------------------------------------------------------
# New checks: max parents + treewidth
# ---------------------------------------------------------------------------


def test_max_parents_metric_reported(gen, checker):
    """max_parents metric is present in check results."""
    world = gen.generate(WorldGenConfig(seed=42))
    result = checker.check(world)
    assert "max_parents" in result.metrics
    assert result.metrics["max_parents"] <= MAX_PARENTS


def test_treewidth_metric_reported(gen, checker):
    """treewidth_upper_bound metric is present in check results."""
    world = gen.generate(WorldGenConfig(seed=42))
    result = checker.check(world)
    assert "treewidth_upper_bound" in result.metrics
    assert result.metrics["treewidth_upper_bound"] >= 0


def test_custom_world_passes_check(checker):
    """A custom world with valid max parents passes WorldCheck."""
    spec = DAGSpec(
        nodes=[
            DAGNodeSpec(name="L1", type=NodeType.LATENT, states=["a", "b"]),
            DAGNodeSpec(name="L2", type=NodeType.LATENT, states=["a", "b", "c"]),
            DAGNodeSpec(name="O1", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
            DAGNodeSpec(name="O2", type=NodeType.OBSERVABLE, states=["lo", "mid", "hi"]),
            DAGNodeSpec(name="O3", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
            DAGNodeSpec(name="T", type=NodeType.TARGET, states=["bad", "ok", "good"]),
        ],
        edges=[
            ("L1", "O1"), ("L1", "O2"),
            ("L2", "O2"), ("L2", "O3"),
            ("O1", "T"), ("O2", "T"),
        ],
    )
    gen = WorldGenTool()
    world = gen.generate_custom(CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=42))
    result = checker.check(world)
    assert result.passed, f"Failures: {result.failures}"
    assert result.metrics["max_parents"] <= MAX_PARENTS


def test_treewidth_warning_not_failure(checker):
    """High treewidth produces a warning, not a failure."""
    # Create a dense graph: 6 nodes all connected to target (but within max parents)
    nodes = [
        DAGNodeSpec(name=f"o{i}", type=NodeType.OBSERVABLE, states=["lo", "hi"])
        for i in range(4)
    ]
    nodes.append(DAGNodeSpec(name="target", type=NodeType.TARGET, states=["lo", "hi"]))
    # Each obs also connected to each other in a chain + cross edges
    edges = [(f"o{i}", "target") for i in range(4)]
    edges.append(("o0", "o1"))
    edges.append(("o0", "o2"))
    edges.append(("o1", "o3"))

    spec = DAGSpec(nodes=nodes, edges=edges)
    gen = WorldGenTool()
    world = gen.generate_custom(CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=42))
    result = checker.check(world)
    # Even if treewidth is high, it should not cause a failure
    tw_failures = [f for f in result.failures if "treewidth" in f.lower()]
    assert len(tw_failures) == 0


def test_chain_low_treewidth(checker):
    """A simple chain has low treewidth (should be 1)."""
    nodes = [
        DAGNodeSpec(name="v0", type=NodeType.LATENT, states=["a", "b"]),
        DAGNodeSpec(name="v1", type=NodeType.OBSERVABLE, states=["a", "b"]),
        DAGNodeSpec(name="v2", type=NodeType.OBSERVABLE, states=["a", "b"]),
        DAGNodeSpec(name="v3", type=NodeType.TARGET, states=["a", "b"]),
    ]
    edges = [("v0", "v1"), ("v1", "v2"), ("v2", "v3")]
    spec = DAGSpec(nodes=nodes, edges=edges)
    gen = WorldGenTool()
    world = gen.generate_custom(CustomWorldGenConfig(dag_spec=spec, edge_strength=0.7, seed=42))
    result = checker.check(world)
    assert result.metrics["treewidth_upper_bound"] <= 2


def test_warnings_field_present(gen, checker):
    """WorldCheckResult has a warnings field."""
    world = gen.generate(WorldGenConfig(seed=42))
    result = checker.check(world)
    assert isinstance(result.warnings, list)
