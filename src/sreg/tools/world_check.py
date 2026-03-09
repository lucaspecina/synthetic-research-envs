"""WorldCheckTool: validates generated worlds for quality and correctness."""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np
from pgmpy.inference import VariableElimination
from pydantic import BaseModel, Field

from sreg.models.dag_spec import MAX_PARENTS
from sreg.models.world import NodeType, World
from sreg.world.pgmpy_utils import world_to_pgmpy

logger = logging.getLogger(__name__)


class WorldCheckResult(BaseModel):
    """Result of world validation."""

    passed: bool
    failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


class WorldCheckTool:
    """Validates that a world meets quality criteria for meaningful inference tasks."""

    def __init__(
        self,
        min_entropy: float = 0.3,
        min_latent: int = 1,
        require_d_separation: bool = True,
    ):
        self.min_entropy = min_entropy
        self.min_latent = min_latent
        self.require_d_separation = require_d_separation

    def check(self, world: World) -> WorldCheckResult:
        failures: list[str] = []
        metrics: dict[str, float] = {}

        latent_nodes = [n for n in world.nodes if n.type == NodeType.LATENT]
        obs_nodes = [n for n in world.nodes if n.type == NodeType.OBSERVABLE]
        target_nodes = [n for n in world.nodes if n.type == NodeType.TARGET]

        # Build DAG
        dag = nx.DiGraph()
        for node in world.nodes:
            dag.add_node(node.name)
        for edge in world.edges:
            dag.add_edge(edge.from_node, edge.to_node)

        # 1. DAG validity
        is_dag = nx.is_directed_acyclic_graph(dag)
        metrics["dag_valid"] = 1.0 if is_dag else 0.0
        if not is_dag:
            failures.append("Graph contains cycles")

        # 2. Minimum latent nodes
        metrics["num_latent"] = float(len(latent_nodes))
        if len(latent_nodes) < self.min_latent:
            failures.append(f"Only {len(latent_nodes)} latent node(s), need >= {self.min_latent}")

        # 3. Path from observables to target
        if target_nodes:
            target_name = target_nodes[0].name
            undirected = dag.to_undirected()
            min_path = float("inf")
            for obs in obs_nodes:
                if nx.has_path(undirected, obs.name, target_name):
                    path_len = nx.shortest_path_length(undirected, obs.name, target_name)
                    min_path = min(min_path, path_len)

            if min_path == float("inf"):
                metrics["min_path_to_target"] = -1.0
                failures.append("No path from any observable to target")
            else:
                metrics["min_path_to_target"] = float(min_path)

        # 4. Prior target entropy
        if target_nodes and is_dag:
            try:
                model = world_to_pgmpy(world)
                ve = VariableElimination(model)
                target_name = target_nodes[0].name
                result = ve.query([target_name])
                probs = result.values.flatten()
                probs = probs[probs > 0]
                entropy = float(-np.sum(probs * np.log2(probs)))
                metrics["prior_target_entropy"] = entropy

                if entropy < self.min_entropy:
                    failures.append(f"Prior target entropy {entropy:.3f} < {self.min_entropy}")
            except Exception as e:
                failures.append(f"Failed to compute entropy: {e}")
                metrics["prior_target_entropy"] = -1.0

        # 5. Non-trivial d-separation
        if self.require_d_separation and is_dag:
            has_d_sep = self._check_d_separation(dag, obs_nodes, latent_nodes)
            metrics["has_d_separation"] = 1.0 if has_d_sep else 0.0
            if not has_d_sep:
                failures.append("No non-trivial d-separation found")

        # 6. Max parents check (hard failure)
        if is_dag:
            max_in = max((dag.in_degree(n) for n in dag.nodes()), default=0)
            metrics["max_parents"] = float(max_in)
            if max_in > MAX_PARENTS:
                violators = [n for n in dag.nodes() if dag.in_degree(n) > MAX_PARENTS]
                failures.append(
                    f"Nodes exceed max parents ({MAX_PARENTS}): "
                    f"{', '.join(f'{n}={dag.in_degree(n)}' for n in violators)}"
                )

        # 7. Treewidth estimate (warning, not failure)
        warnings: list[str] = []
        if is_dag:
            tw = self._estimate_treewidth(dag)
            metrics["treewidth_upper_bound"] = float(tw)
            if tw > 8:
                warnings.append(
                    f"High treewidth ({tw}) may cause slow inference. "
                    f"Consider reducing connectivity or adding mediators."
                )

        return WorldCheckResult(
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
            metrics=metrics,
        )

    def _check_d_separation(
        self,
        dag: nx.DiGraph,
        obs_nodes: list,
        latent_nodes: list,
    ) -> bool:
        """Check for at least one non-trivial d-separation.

        Tries conditioning on latent nodes first (star structures),
        then on individual observables (chain structures where
        conditioning on an intermediate node blocks the path).
        """
        if len(obs_nodes) < 2:
            return False

        obs_names = [n.name for n in obs_nodes]

        # Build conditioning sets to try: latents, then each individual observable
        cond_sets = [frozenset(n.name for n in latent_nodes)]
        for obs in obs_names:
            cond_sets.append(frozenset([obs]))

        for cond_set in cond_sets:
            for i, n1 in enumerate(obs_names):
                if n1 in cond_set:
                    continue
                for n2 in obs_names[i + 1 :]:
                    if n2 in cond_set:
                        continue
                    try:
                        if nx.is_d_separator(dag, n1, n2, cond_set):
                            return True
                    except nx.NetworkXError:
                        continue
        return False

    @staticmethod
    def _estimate_treewidth(dag: nx.DiGraph) -> int:
        """Estimate treewidth upper bound via min-fill heuristic on the moral graph.

        Treewidth determines the complexity of exact inference (Variable Elimination).
        This returns an upper bound, not the exact treewidth.
        """
        # Moralize: add edges between co-parents, then drop direction
        moral = dag.to_undirected()
        for node in dag.nodes():
            parents = list(dag.predecessors(node))
            for i, p1 in enumerate(parents):
                for p2 in parents[i + 1 :]:
                    moral.add_edge(p1, p2)

        # Min-fill elimination: greedily eliminate the node that adds fewest fill edges
        g = moral.copy()
        max_clique_size = 0
        for _ in range(len(g)):
            if not g.nodes():
                break
            # Pick node with minimum fill edges
            best_node = min(g.nodes(), key=lambda n: _fill_count(g, n))
            neighbors = set(g.neighbors(best_node))
            clique_size = len(neighbors) + 1  # neighbors + the node itself
            max_clique_size = max(max_clique_size, clique_size)
            # Add fill edges
            nbrs = list(neighbors)
            for i, n1 in enumerate(nbrs):
                for n2 in nbrs[i + 1 :]:
                    g.add_edge(n1, n2)
            g.remove_node(best_node)

        return max_clique_size - 1  # treewidth = max clique size - 1


def _fill_count(g: nx.Graph, node: str) -> int:
    """Count how many fill edges would be added by eliminating this node."""
    neighbors = list(g.neighbors(node))
    count = 0
    for i, n1 in enumerate(neighbors):
        for n2 in neighbors[i + 1 :]:
            if not g.has_edge(n1, n2):
                count += 1
    return count


__all__ = ["WorldCheckResult", "WorldCheckTool"]
