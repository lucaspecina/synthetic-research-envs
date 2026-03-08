"""Causal chain template: linear chain of variables leading to a target."""

from __future__ import annotations

import numpy as np

from sreg.models.world import CPD, DifficultyProfile, Edge, Node, NodeType, World

STATE_LABELS: dict[int, list[str]] = {
    2: ["low", "high"],
    3: ["low", "medium", "high"],
    4: ["low", "medium_low", "medium_high", "high"],
    5: ["very_low", "low", "medium", "high", "very_high"],
}


class CausalChainTemplate:
    """Linear causal chain: root → stage_1 → stage_2 → ... → target.

    Structure:
        root_cause → stage_1 → stage_2 → ... → stage_N → target_outcome

    The first `num_latent` nodes are hidden. The rest are observable.
    The agent must figure out that observing nodes closer to the target
    in the chain provides more information than distant nodes.
    """

    def generate(
        self,
        *,
        seed: int,
        num_nodes: int,
        num_latent: int,
        num_states: int,
        edge_strength: float,
    ) -> World:
        rng = np.random.default_rng(seed)
        states = STATE_LABELS[num_states]
        num_observable = num_nodes - num_latent - 1  # -1 for target

        nodes = self._create_nodes(num_latent, num_observable, states)
        edges = self._create_edges(nodes)
        cpds = self._create_cpds(nodes, edges, states, edge_strength, rng)
        difficulty = self._build_difficulty(
            num_nodes, num_latent, num_observable, len(edges), num_states, edge_strength
        )

        return World(
            id=f"world-{seed:06d}",
            seed=seed,
            template_family="causal_chain",
            description=(
                f"Causal chain world with {num_nodes} nodes "
                f"({num_latent} latent, {num_observable} observable, 1 target)"
            ),
            nodes=nodes,
            edges=edges,
            cpds=cpds,
            difficulty=difficulty,
        )

    def _create_nodes(
        self, num_latent: int, num_observable: int, states: list[str]
    ) -> list[Node]:
        nodes: list[Node] = []

        # Latent nodes at the start of the chain
        for i in range(num_latent):
            suffix = f"_{i + 1}" if num_latent > 1 else ""
            nodes.append(
                Node(
                    name=f"root_cause{suffix}",
                    type=NodeType.LATENT,
                    description=f"Unobservable root cause{suffix}",
                    states=list(states),
                )
            )

        # Observable intermediate nodes
        for i in range(num_observable):
            nodes.append(
                Node(
                    name=f"stage_{i + 1}",
                    type=NodeType.OBSERVABLE,
                    description=f"Observable intermediate stage {i + 1}",
                    states=list(states),
                )
            )

        # Target at the end of the chain
        nodes.append(
            Node(
                name="target_outcome",
                type=NodeType.TARGET,
                description="Target variable to predict",
                states=list(states),
            )
        )
        return nodes

    def _create_edges(self, nodes: list[Node]) -> list[Edge]:
        """Create a linear chain: node_0 → node_1 → ... → node_N."""
        edges: list[Edge] = []
        for i in range(len(nodes) - 1):
            edges.append(
                Edge(
                    from_node=nodes[i].name,
                    to_node=nodes[i + 1].name,
                    mechanism=f"{nodes[i].name} causes {nodes[i + 1].name}",
                )
            )
        return edges

    def _create_cpds(
        self,
        nodes: list[Node],
        edges: list[Edge],
        states: list[str],
        edge_strength: float,
        rng: np.random.Generator,
    ) -> list[CPD]:
        parent_map: dict[str, list[str]] = {n.name: [] for n in nodes}
        for edge in edges:
            parent_map[edge.to_node].append(edge.from_node)

        cpds: list[CPD] = []
        for node in nodes:
            parents = parent_map[node.name]
            num_states = len(states)

            state_names: dict[str, list[str]] = {node.name: list(states)}
            for p in parents:
                state_names[p] = list(states)

            if not parents:
                table = self._root_cpd(num_states, rng)
            else:
                parent_cards = [num_states] * len(parents)
                table = self._child_cpd(num_states, parent_cards, edge_strength, rng)

            cpds.append(
                CPD(node=node.name, parents=parents, table=table, state_names=state_names)
            )
        return cpds

    def _root_cpd(self, num_states: int, rng: np.random.Generator) -> list[list[float]]:
        alpha = rng.uniform(1.0, 4.0, size=num_states)
        probs = rng.dirichlet(alpha)
        return [[float(p)] for p in probs]

    def _child_cpd(
        self,
        num_states: int,
        parent_cards: list[int],
        edge_strength: float,
        rng: np.random.Generator,
    ) -> list[list[float]]:
        """CPD for a child node — same formula as latent_preference."""
        num_combos = 1
        for c in parent_cards:
            num_combos *= c

        perms = [rng.permutation(num_states) for _ in parent_cards]
        table = np.zeros((num_states, num_combos))

        for col_idx in range(num_combos):
            parent_indices = []
            temp = col_idx
            for card in reversed(parent_cards):
                parent_indices.insert(0, temp % card)
                temp //= card

            votes = np.zeros(num_states)
            for p_idx, p_state in enumerate(parent_indices):
                mapped = perms[p_idx][p_state % num_states]
                votes[mapped] += 1
            dominant = int(np.argmax(votes))

            base = max(0.1, (1.0 - edge_strength) * 2.0)
            alpha = np.full(num_states, base)
            alpha[dominant] += edge_strength * 15.0
            probs = rng.dirichlet(alpha)
            table[:, col_idx] = probs

        return table.tolist()

    def _build_difficulty(
        self,
        num_nodes: int,
        num_latent: int,
        num_observable: int,
        num_edges: int,
        num_states: int,
        edge_strength: float,
    ) -> DifficultyProfile:
        max_edges = num_nodes * (num_nodes - 1) / 2
        # Chains are harder because info degrades along the chain
        if edge_strength >= 0.8:
            level = "easy"
        elif edge_strength >= 0.5:
            level = "medium"
        else:
            level = "hard"

        return DifficultyProfile(
            level=level,
            num_nodes=num_nodes,
            num_latent=num_latent,
            num_observable=num_observable,
            edge_density=num_edges / max_edges if max_edges > 0 else 0.0,
            avg_states_per_node=float(num_states),
        )


__all__ = ["CausalChainTemplate"]
