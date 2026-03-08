"""Fork-collider template: common cause + collider structure."""

from __future__ import annotations

import numpy as np

from sreg.models.world import CPD, DifficultyProfile, Edge, Node, NodeType, World

STATE_LABELS: dict[int, list[str]] = {
    2: ["low", "high"],
    3: ["low", "medium", "high"],
    4: ["low", "medium_low", "medium_high", "high"],
    5: ["very_low", "low", "medium", "high", "very_high"],
}


class ForkColliderTemplate:
    """Fork (common cause) with a collider downstream.

    Structure (6 nodes, 1 latent):
        hidden_factor (LATENT)
          ↙            ↘
      branch_1 (O)   branch_2 (O)
          ↘            ↙
          collider (O)         ← explaining away
              ↓
          target_outcome (T)

    With more nodes: extra branches (3+) or mediators between collider and target.

    Key properties:
    - Fork: hidden_factor → branch_1, branch_2 (marginal correlation)
    - Collider: branch_1, branch_2 → collider (conditioning activates dependency)
    - The agent must understand that observing the collider changes
      how informative the branches are (Berkson's paradox / explaining away)

    Minimum num_nodes: num_latent + 4 (2 branches + 1 collider + 1 target).
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

        min_needed = num_latent + 4  # branches(2) + collider + target
        if num_nodes < min_needed:
            raise ValueError(
                f"fork_collider needs at least {min_needed} nodes "
                f"({num_latent} latent + 2 branches + 1 collider + 1 target), "
                f"got {num_nodes}"
            )

        nodes, structure = self._create_nodes(num_nodes, num_latent, states)
        edges = self._create_edges(nodes, structure)
        cpds = self._create_cpds(nodes, edges, states, edge_strength, rng)
        num_observable = sum(1 for n in nodes if n.type == NodeType.OBSERVABLE)
        difficulty = self._build_difficulty(
            num_nodes, num_latent, num_observable, len(edges), num_states, edge_strength
        )

        return World(
            id=f"world-{seed:06d}",
            seed=seed,
            template_family="fork_collider",
            description=(
                f"Fork-collider world with {num_nodes} nodes "
                f"({num_latent} latent, {num_observable} observable, 1 target)"
            ),
            nodes=nodes,
            edges=edges,
            cpds=cpds,
            difficulty=difficulty,
        )

    def _create_nodes(
        self, num_nodes: int, num_latent: int, states: list[str]
    ) -> tuple[list[Node], dict]:
        """Create nodes and return structure info for edge creation."""
        # Allocate: latents + branches + collider + mediators + target
        # branches: at least 2, up to 3 if enough nodes
        remaining = num_nodes - num_latent - 1 - 1  # minus collider, minus target
        num_branches = min(3, max(2, remaining))
        num_mediators = remaining - num_branches

        nodes: list[Node] = []

        # Latent fork parents
        latent_names = []
        for i in range(num_latent):
            suffix = f"_{i + 1}" if num_latent > 1 else ""
            name = f"hidden_factor{suffix}"
            latent_names.append(name)
            nodes.append(
                Node(
                    name=name,
                    type=NodeType.LATENT,
                    description=f"Unobservable common cause{suffix}",
                    states=list(states),
                )
            )

        # Branch nodes (fork children, collider parents)
        branch_names = []
        for i in range(num_branches):
            name = f"branch_{i + 1}"
            branch_names.append(name)
            nodes.append(
                Node(
                    name=name,
                    type=NodeType.OBSERVABLE,
                    description=f"Observable branch {i + 1}",
                    states=list(states),
                )
            )

        # Collider node
        nodes.append(
            Node(
                name="collider",
                type=NodeType.OBSERVABLE,
                description="Collider variable (effect of multiple causes)",
                states=list(states),
            )
        )

        # Mediator nodes (between collider and target)
        mediator_names = []
        for i in range(num_mediators):
            name = f"mediator_{i + 1}"
            mediator_names.append(name)
            nodes.append(
                Node(
                    name=name,
                    type=NodeType.OBSERVABLE,
                    description=f"Mediator variable {i + 1}",
                    states=list(states),
                )
            )

        # Target
        nodes.append(
            Node(
                name="target_outcome",
                type=NodeType.TARGET,
                description="Target variable to predict",
                states=list(states),
            )
        )

        structure = {
            "latent_names": latent_names,
            "branch_names": branch_names,
            "mediator_names": mediator_names,
        }
        return nodes, structure

    def _create_edges(self, nodes: list[Node], structure: dict) -> list[Edge]:
        latent_names = structure["latent_names"]
        branch_names = structure["branch_names"]
        mediator_names = structure["mediator_names"]

        edges: list[Edge] = []

        # Fork: each latent → all branches (round-robin if multiple latents)
        for i, branch in enumerate(branch_names):
            parent = latent_names[i % len(latent_names)]
            edges.append(
                Edge(
                    from_node=parent,
                    to_node=branch,
                    mechanism=f"{parent} causes {branch}",
                )
            )

        # Collider: all branches → collider
        for branch in branch_names:
            edges.append(
                Edge(
                    from_node=branch,
                    to_node="collider",
                    mechanism=f"{branch} contributes to collider",
                )
            )

        # Chain from collider through mediators to target
        chain = ["collider"] + mediator_names + ["target_outcome"]
        for i in range(len(chain) - 1):
            edges.append(
                Edge(
                    from_node=chain[i],
                    to_node=chain[i + 1],
                    mechanism=f"{chain[i]} influences {chain[i + 1]}",
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
        """Same CPD formula as other templates."""
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
        # Colliders make reasoning harder at any edge_strength
        if edge_strength >= 0.8:
            level = "medium"
        elif edge_strength >= 0.5:
            level = "hard"
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


__all__ = ["ForkColliderTemplate"]
