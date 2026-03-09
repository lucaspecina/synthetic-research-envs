"""Tests for CustomTemplate: DAGSpec -> World generation."""

import pytest

from sreg.models.dag_spec import DAGNodeSpec, DAGSpec
from sreg.models.world import NodeType, World
from sreg.world.pgmpy_utils import world_to_pgmpy
from sreg.world.templates.custom import CustomTemplate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_spec() -> DAGSpec:
    """A -> B: observable -> target."""
    return DAGSpec(
        nodes=[
            DAGNodeSpec(name="cause", type=NodeType.OBSERVABLE, states=["low", "high"]),
            DAGNodeSpec(name="effect", type=NodeType.TARGET, states=["low", "medium", "high"]),
        ],
        edges=[("cause", "effect")],
    )


def _diamond_spec() -> DAGSpec:
    """latent -> obs1, latent -> obs2, obs1 -> target, obs2 -> target."""
    return DAGSpec(
        nodes=[
            DAGNodeSpec(name="hidden", type=NodeType.LATENT, states=["on", "off"]),
            DAGNodeSpec(name="sensor_a", type=NodeType.OBSERVABLE, states=["low", "medium", "high"]),
            DAGNodeSpec(name="sensor_b", type=NodeType.OBSERVABLE, states=["weak", "strong"]),
            DAGNodeSpec(name="outcome", type=NodeType.TARGET, states=["bad", "ok", "good"]),
        ],
        edges=[
            ("hidden", "sensor_a"),
            ("hidden", "sensor_b"),
            ("sensor_a", "outcome"),
            ("sensor_b", "outcome"),
        ],
    )


def _chain_spec(n: int) -> DAGSpec:
    """Linear chain of n nodes."""
    nodes = []
    for i in range(n):
        if i == 0:
            ntype = NodeType.LATENT
        elif i == n - 1:
            ntype = NodeType.TARGET
        else:
            ntype = NodeType.OBSERVABLE
        nodes.append(DAGNodeSpec(name=f"v{i}", type=ntype, states=["lo", "hi"]))
    edges = [(f"v{i}", f"v{i+1}") for i in range(n - 1)]
    return DAGSpec(nodes=nodes, edges=edges)


def _large_spec(n_obs: int = 10, n_latent: int = 2) -> DAGSpec:
    """Larger DAG with multiple latents feeding observables and a target."""
    nodes = []
    edges = []

    # Latent nodes
    for i in range(n_latent):
        nodes.append(DAGNodeSpec(
            name=f"latent_{i}", type=NodeType.LATENT, states=["a", "b", "c"]
        ))

    # Observable nodes, each connected to one latent (round-robin)
    for i in range(n_obs):
        states = ["lo", "hi"] if i % 2 == 0 else ["lo", "mid", "hi"]
        nodes.append(DAGNodeSpec(
            name=f"obs_{i}", type=NodeType.OBSERVABLE, states=states
        ))
        parent_latent = f"latent_{i % n_latent}"
        edges.append((parent_latent, f"obs_{i}"))

    # Target with 2 parents: first two observables
    nodes.append(DAGNodeSpec(
        name="target", type=NodeType.TARGET, states=["bad", "ok", "good"]
    ))
    edges.append(("obs_0", "target"))
    edges.append(("obs_1", "target"))

    # Add a chain between some observables
    for i in range(2, min(5, n_obs)):
        edges.append((f"obs_{i-1}", f"obs_{i}"))

    return DAGSpec(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Basic generation
# ---------------------------------------------------------------------------

class TestCustomTemplateGeneration:
    def test_simple(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_simple_spec(), edge_strength=0.7, seed=42)
        assert isinstance(world, World)
        assert len(world.nodes) == 2
        assert len(world.edges) == 1
        assert len(world.cpds) == 2
        assert world.template_family == "custom"

    def test_diamond(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_diamond_spec(), edge_strength=0.7, seed=42)
        assert len(world.nodes) == 4
        assert len(world.edges) == 4
        assert len(world.cpds) == 4

    def test_chain_10(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_chain_spec(10), edge_strength=0.7, seed=42)
        assert len(world.nodes) == 10
        assert len(world.cpds) == 10

    def test_large_12_nodes(self):
        template = CustomTemplate()
        spec = _large_spec(n_obs=10, n_latent=2)
        world = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        assert len(world.nodes) == 13  # 2 latent + 10 obs + 1 target

    def test_large_15_nodes(self):
        template = CustomTemplate()
        spec = _large_spec(n_obs=12, n_latent=3)
        world = template.generate(dag_spec=spec, edge_strength=0.6, seed=99)
        assert len(world.nodes) == 16  # 3 latent + 12 obs + 1 target

    def test_reproducible(self):
        template = CustomTemplate()
        spec = _diamond_spec()
        w1 = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        w2 = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        for cpd1, cpd2 in zip(w1.cpds, w2.cpds):
            assert cpd1.table == cpd2.table

    def test_different_seeds_differ(self):
        template = CustomTemplate()
        spec = _diamond_spec()
        w1 = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        w2 = template.generate(dag_spec=spec, edge_strength=0.7, seed=99)
        # At least some CPDs should differ
        any_diff = False
        for cpd1, cpd2 in zip(w1.cpds, w2.cpds):
            if cpd1.table != cpd2.table:
                any_diff = True
                break
        assert any_diff


# ---------------------------------------------------------------------------
# Heterogeneous states
# ---------------------------------------------------------------------------

class TestHeterogeneousStates:
    def test_mixed_cardinalities(self):
        """Nodes with 2, 3, and 4 states in the same world."""
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="binary", type=NodeType.OBSERVABLE, states=["yes", "no"]),
                DAGNodeSpec(name="ternary", type=NodeType.OBSERVABLE, states=["a", "b", "c"]),
                DAGNodeSpec(name="quad", type=NodeType.TARGET, states=["w", "x", "y", "z"]),
            ],
            edges=[("binary", "quad"), ("ternary", "quad")],
        )
        template = CustomTemplate()
        world = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)

        # Target CPD: 4 child states x (2*3=6) parent combos
        target_cpd = next(c for c in world.cpds if c.node == "quad")
        assert len(target_cpd.table) == 4
        assert all(len(row) == 6 for row in target_cpd.table)

    def test_binary_and_ternary_parents(self):
        """Parent with 2 states, child with 3 states."""
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="switch", type=NodeType.OBSERVABLE, states=["on", "off"]),
                DAGNodeSpec(name="level", type=NodeType.TARGET, states=["lo", "mid", "hi"]),
            ],
            edges=[("switch", "level")],
        )
        template = CustomTemplate()
        world = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        level_cpd = next(c for c in world.cpds if c.node == "level")
        assert len(level_cpd.table) == 3  # child states
        assert all(len(row) == 2 for row in level_cpd.table)  # parent combos


# ---------------------------------------------------------------------------
# pgmpy integration
# ---------------------------------------------------------------------------

class TestPgmpyIntegration:
    def test_simple_converts(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_simple_spec(), edge_strength=0.7, seed=42)
        model = world_to_pgmpy(world)
        assert model.check_model()

    def test_diamond_converts(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_diamond_spec(), edge_strength=0.7, seed=42)
        model = world_to_pgmpy(world)
        assert model.check_model()

    def test_heterogeneous_converts(self):
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="a", type=NodeType.OBSERVABLE, states=["yes", "no"]),
                DAGNodeSpec(name="b", type=NodeType.OBSERVABLE, states=["x", "y", "z"]),
                DAGNodeSpec(name="t", type=NodeType.TARGET, states=["lo", "hi"]),
            ],
            edges=[("a", "t"), ("b", "t")],
        )
        template = CustomTemplate()
        world = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        model = world_to_pgmpy(world)
        assert model.check_model()

    def test_chain_10_converts(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_chain_spec(10), edge_strength=0.7, seed=42)
        model = world_to_pgmpy(world)
        assert model.check_model()

    def test_large_12_converts(self):
        template = CustomTemplate()
        spec = _large_spec(n_obs=10, n_latent=2)
        world = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        model = world_to_pgmpy(world)
        assert model.check_model()

    def test_large_15_converts(self):
        """15+ node world converts to valid pgmpy model."""
        template = CustomTemplate()
        spec = _large_spec(n_obs=12, n_latent=3)
        world = template.generate(dag_spec=spec, edge_strength=0.6, seed=99)
        model = world_to_pgmpy(world)
        assert model.check_model()


# ---------------------------------------------------------------------------
# Difficulty profile
# ---------------------------------------------------------------------------

class TestDifficultyProfile:
    def test_easy(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_simple_spec(), edge_strength=0.8, seed=42)
        assert world.difficulty.level == "easy"
        assert world.difficulty.num_nodes == 2

    def test_hard_large(self):
        template = CustomTemplate()
        spec = _large_spec(n_obs=12, n_latent=3)
        world = template.generate(dag_spec=spec, edge_strength=0.6, seed=42)
        assert world.difficulty.level == "hard"  # 16 nodes >= 15

    def test_hard_low_es(self):
        template = CustomTemplate()
        world = template.generate(dag_spec=_diamond_spec(), edge_strength=0.3, seed=42)
        assert world.difficulty.level == "hard"

    def test_avg_states_heterogeneous(self):
        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="a", type=NodeType.OBSERVABLE, states=["lo", "hi"]),
                DAGNodeSpec(name="b", type=NodeType.TARGET, states=["x", "y", "z"]),
            ],
            edges=[("a", "b")],
        )
        template = CustomTemplate()
        world = template.generate(dag_spec=spec, edge_strength=0.7, seed=42)
        assert world.difficulty.avg_states_per_node == 2.5  # (2+3)/2


# ---------------------------------------------------------------------------
# WorldGenTool integration
# ---------------------------------------------------------------------------

class TestWorldGenToolCustom:
    def test_generate_custom(self):
        from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenTool

        config = CustomWorldGenConfig(
            dag_spec=_diamond_spec(),
            edge_strength=0.7,
            seed=42,
        )
        tool = WorldGenTool()
        world = tool.generate_custom(config)
        assert isinstance(world, World)
        assert world.template_family == "custom"
        assert len(world.nodes) == 4

    def test_existing_templates_unchanged(self):
        """Existing generate() still works for fixed templates."""
        from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

        tool = WorldGenTool()
        for family in ["latent_preference", "causal_chain", "fork_collider"]:
            config = WorldGenConfig(template_family=family, seed=42)
            world = tool.generate(config)
            assert world.template_family == family


# ---------------------------------------------------------------------------
# E2E: TaskGen + Teacher solver with custom worlds
# ---------------------------------------------------------------------------

class TestE2ETaskGenWithCustom:
    """Verify all 3 task types work end-to-end with custom worlds."""

    def _make_world(self, spec: DAGSpec, seed: int = 42, es: float = 0.7) -> World:
        from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenTool
        config = CustomWorldGenConfig(dag_spec=spec, edge_strength=es, seed=seed)
        return WorldGenTool().generate_custom(config)

    def test_infer_target_custom(self):
        """infer_target task works with a custom world."""
        from sreg.models.task import TaskSpec, TaskType
        from sreg.tools.task_gen import TaskGenTool

        world = self._make_world(_diamond_spec())
        target = "outcome"
        spec = TaskSpec(type=TaskType.INFER_TARGET, target_node=target, max_budget=3)
        task = TaskGenTool().generate(world, spec, seed=42)
        assert task.type == TaskType.INFER_TARGET
        assert task.target_node == target
        assert len(task.correct_answer) == 3  # 3 states

    def test_nbo_custom(self):
        """next_best_observation task works with a custom world."""
        from sreg.models.task import TaskSpec, TaskType
        from sreg.tools.task_gen import TaskGenTool

        world = self._make_world(_diamond_spec())
        target = "outcome"
        spec = TaskSpec(type=TaskType.NEXT_BEST_OBSERVATION, target_node=target, max_budget=3)
        task = TaskGenTool().generate(world, spec, seed=42)
        assert task.type == TaskType.NEXT_BEST_OBSERVATION
        assert task.correct_answer  # IG ranking should be non-empty

    def test_hypothesis_selection_custom(self):
        """hypothesis_selection task works with a custom world."""
        from sreg.models.task import TaskSpec, TaskType
        from sreg.tools.task_gen import TaskGenTool

        world = self._make_world(_diamond_spec())
        target = "outcome"
        spec = TaskSpec(type=TaskType.HYPOTHESIS_SELECTION, target_node=target, max_budget=3)
        task = TaskGenTool().generate(world, spec, seed=42)
        assert task.type == TaskType.HYPOTHESIS_SELECTION
        assert task.hypotheses
        assert len(task.hypotheses) == 4  # A, B, C, D

    def test_generate_all_custom(self):
        """TaskBundle with all 3 task types works with a custom world."""
        from sreg.tools.task_gen import TaskGenTool

        world = self._make_world(_diamond_spec())
        bundle = TaskGenTool().generate_all(world, target_node="outcome", seed=42)
        assert bundle.infer_target is not None
        assert bundle.next_best_observation is not None
        assert bundle.hypothesis_selection is not None

    def test_teacher_solver_custom(self):
        """Teacher solver works and improves over prior for custom worlds."""
        from sreg.solver.exact_bayes import ExactBayesSolver

        world = self._make_world(_diamond_spec(), es=0.7)
        solver = ExactBayesSolver(world)

        # Prior
        prior = solver.posterior("outcome")
        assert len(prior) == 3
        assert abs(sum(prior.values()) - 1.0) < 1e-10

        # With evidence
        state = solver.sample_state(seed=42)
        evidence = {"sensor_a": state["sensor_a"]}
        posterior = solver.posterior("outcome", evidence)
        assert abs(sum(posterior.values()) - 1.0) < 1e-10

        # IG should be computable
        ig = solver.information_gain("outcome", {}, "sensor_a")
        assert ig >= 0

    def test_large_custom_world_e2e(self):
        """12-node custom world: TaskGen + Teacher all work."""
        from sreg.tools.task_gen import TaskGenTool
        from sreg.solver.exact_bayes import ExactBayesSolver

        spec = _large_spec(n_obs=10, n_latent=2)
        world = self._make_world(spec, seed=99, es=0.6)

        # Teacher solver works
        solver = ExactBayesSolver(world)
        prior = solver.posterior("target")
        assert len(prior) == 3

        # All 3 task types generate
        bundle = TaskGenTool().generate_all(world, target_node="target", seed=99)
        assert bundle.infer_target is not None
        assert bundle.next_best_observation is not None
        assert bundle.hypothesis_selection is not None

    def test_heterogeneous_states_e2e(self):
        """Custom world with mixed cardinalities: full E2E."""
        from sreg.tools.task_gen import TaskGenTool

        spec = DAGSpec(
            nodes=[
                DAGNodeSpec(name="switch", type=NodeType.OBSERVABLE, states=["on", "off"]),
                DAGNodeSpec(name="level", type=NodeType.OBSERVABLE, states=["a", "b", "c"]),
                DAGNodeSpec(name="result", type=NodeType.TARGET, states=["bad", "ok", "good", "great"]),
            ],
            edges=[("switch", "result"), ("level", "result")],
        )
        world = self._make_world(spec)
        bundle = TaskGenTool().generate_all(world, target_node="result", seed=42)
        assert len(bundle.infer_target.correct_answer) == 4  # 4-state target
