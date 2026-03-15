"""Custom template: generates a World from any valid DAGSpec.

This is the bridge between arbitrary DAG structures and the existing
World model. It accepts a DAGSpec (nodes + edges), generates CPDs
using the generic edge_strength formula, and produces a fully valid World.

Supports heterogeneous state cardinalities: each node can have a different
number of states.
"""

from __future__ import annotations

import numpy as np

from sreg.models.dag_spec import DAGSpec
from sreg.models.world import DifficultyProfile, Edge, Node, NodeType, World
from sreg.world.cpd_gen import generate_cpds_for_dag


class CustomTemplate:
    """Generates a World from an arbitrary DAGSpec.

    Unlike the fixed templates (latent_preference, causal_chain, fork_collider),
    this template accepts any valid DAG structure and generates CPDs for it.
    """

    def generate(
        self,
        *,
        dag_spec: DAGSpec,
        edge_strength: float,
        seed: int,
        edge_directions: dict[tuple[str, str], str] | None = None,
    ) -> World:
        """Generate a World from a DAGSpec.

        Parameters
        ----------
        dag_spec : DAGSpec
            The DAG structure (nodes + edges). Must pass all DAGSpec validations.
        edge_strength : float
            Controls signal strength in CPDs (0.0 = weak, 1.0 = strong).
        seed : int
            Random seed for reproducibility.
        edge_directions : dict | None
            Optional {(parent, child): "positive"|"negative"} mapping.
            Controls effect direction in CPDs.

        Returns
        -------
        World
            A complete World with nodes, edges, CPDs, and difficulty profile.
        """
        rng = np.random.default_rng(seed)

        nodes = self._create_nodes(dag_spec)
        edges = self._create_edges(dag_spec)
        cpds = self._create_cpds(dag_spec, edge_strength, rng, edge_directions)
        difficulty = self._build_difficulty(dag_spec, edge_strength)

        return World(
            id=f"world-custom-{seed:06d}",
            seed=seed,
            template_family="custom",
            description=(
                f"Custom world with {len(dag_spec.nodes)} nodes "
                f"({len(dag_spec.nodes_by_type(NodeType.LATENT))} latent, "
                f"{len(dag_spec.nodes_by_type(NodeType.OBSERVABLE))} observable, "
                f"{len(dag_spec.nodes_by_type(NodeType.TARGET))} target)"
            ),
            nodes=nodes,
            edges=edges,
            cpds=cpds,
            difficulty=difficulty,
        )

    def _create_nodes(self, dag_spec: DAGSpec) -> list[Node]:
        return [
            Node(
                name=n.name,
                type=n.type,
                description=f"{n.type.value} variable: {n.name}",
                states=list(n.states),
            )
            for n in dag_spec.nodes
        ]

    def _create_edges(self, dag_spec: DAGSpec) -> list[Edge]:
        return [
            Edge(
                from_node=src,
                to_node=dst,
                mechanism=f"{src} influences {dst}",
            )
            for src, dst in dag_spec.edges
        ]

    def _create_cpds(
        self,
        dag_spec: DAGSpec,
        edge_strength: float,
        rng: np.random.Generator,
        edge_directions: dict[tuple[str, str], str] | None = None,
    ) -> list:
        parent_map: dict[str, list[str]] = {n.name: [] for n in dag_spec.nodes}
        for src, dst in dag_spec.edges:
            parent_map[dst].append(src)

        node_states = {n.name: list(n.states) for n in dag_spec.nodes}
        nodes_tuples = [(n.name, list(n.states)) for n in dag_spec.nodes]

        return generate_cpds_for_dag(
            nodes_tuples, parent_map, node_states, edge_strength, rng,
            edge_directions=edge_directions,
        )

    def _build_difficulty(self, dag_spec: DAGSpec, edge_strength: float) -> DifficultyProfile:
        num_nodes = len(dag_spec.nodes)
        num_latent = len(dag_spec.nodes_by_type(NodeType.LATENT))
        num_observable = len(dag_spec.nodes_by_type(NodeType.OBSERVABLE))
        num_edges = len(dag_spec.edges)
        max_edges = num_nodes * (num_nodes - 1) / 2

        # Difficulty heuristic: accounts for size, edge_strength, and latent ratio
        latent_ratio = num_latent / num_nodes if num_nodes > 0 else 0
        if edge_strength >= 0.7 and num_nodes <= 8 and latent_ratio <= 0.2:
            level = "easy"
        elif edge_strength <= 0.4 or num_nodes >= 15 or latent_ratio >= 0.3:
            level = "hard"
        else:
            level = "medium"

        avg_states = sum(len(n.states) for n in dag_spec.nodes) / num_nodes

        return DifficultyProfile(
            level=level,
            num_nodes=num_nodes,
            num_latent=num_latent,
            num_observable=num_observable,
            edge_density=num_edges / max_edges if max_edges > 0 else 0.0,
            avg_states_per_node=avg_states,
        )


__all__ = ["CustomTemplate"]
