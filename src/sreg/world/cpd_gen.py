"""Generic CPD generation for arbitrary DAG structures.

Extracted from the three v1 templates (latent_preference, causal_chain,
fork_collider) which all use identical CPD generation logic. This module
makes that logic reusable for any DAGSpec.

Supports heterogeneous state cardinalities: each node can have a different
number of states (e.g., 2 and 3 mixed in the same world).
"""

from __future__ import annotations

import numpy as np

from sreg.models.world import CPD

STATE_LABELS: dict[int, list[str]] = {
    2: ["low", "high"],
    3: ["low", "medium", "high"],
    4: ["low", "medium_low", "medium_high", "high"],
    5: ["very_low", "low", "medium", "high", "very_high"],
}


def generate_root_cpd(num_states: int, rng: np.random.Generator) -> list[list[float]]:
    """Non-uniform marginal for root nodes (no parents).

    Samples from Dirichlet with random alpha in [1.0, 4.0] per state,
    producing a non-uniform but not extreme distribution.
    """
    alpha = rng.uniform(1.0, 4.0, size=num_states)
    probs = rng.dirichlet(alpha)
    return [[float(p)] for p in probs]


def generate_child_cpd(
    num_child_states: int,
    parent_cards: list[int],
    edge_strength: float,
    rng: np.random.Generator,
) -> list[list[float]]:
    """CPD for a child node given its parents, controlled by edge_strength.

    For each parent state combination, determines a dominant child state
    via a permutation-voting mechanism, then samples from a Dirichlet
    distribution peaked at the dominant state.

    Supports heterogeneous parent cardinalities: each parent can have
    a different number of states.

    Parameters
    ----------
    num_child_states : int
        Number of states of the child node.
    parent_cards : list[int]
        Cardinality (number of states) of each parent, in order.
    edge_strength : float
        Controls how peaked CPDs are. 0.0 = near-uniform (weak signal),
        1.0 = very peaked (strong signal).
    rng : np.random.Generator
        Random number generator.

    Returns
    -------
    list[list[float]]
        CPD table: rows = child states, cols = parent state combinations.
    """
    num_combos = 1
    for c in parent_cards:
        num_combos *= c

    # Each parent gets a permutation mapping parent states to child states.
    # When parent has more states than child, modular wrapping is used.
    perms = [rng.permutation(num_child_states) for _ in parent_cards]

    table = np.zeros((num_child_states, num_combos))

    for col_idx in range(num_combos):
        # Decode parent state indices (first parent varies slowest)
        parent_indices: list[int] = []
        temp = col_idx
        for card in reversed(parent_cards):
            parent_indices.insert(0, temp % card)
            temp //= card

        # Determine dominant child state via parent "votes"
        votes = np.zeros(num_child_states)
        for p_idx, p_state in enumerate(parent_indices):
            mapped = perms[p_idx][p_state % num_child_states]
            votes[mapped] += 1
        dominant = int(np.argmax(votes))

        # Generate Dirichlet distribution peaked at dominant
        base = max(0.1, (1.0 - edge_strength) * 2.0)
        alpha = np.full(num_child_states, base)
        alpha[dominant] += edge_strength * 15.0
        probs = rng.dirichlet(alpha)
        table[:, col_idx] = probs

    return table.tolist()


def generate_cpds_for_dag(
    nodes: list[tuple[str, list[str]]],
    parent_map: dict[str, list[str]],
    node_states: dict[str, list[str]],
    edge_strength: float,
    rng: np.random.Generator,
) -> list[CPD]:
    """Generate CPDs for all nodes in a DAG.

    Parameters
    ----------
    nodes : list[tuple[str, list[str]]]
        List of (node_name, states) pairs, in topological order preferred.
    parent_map : dict[str, list[str]]
        Mapping from node name to list of parent names.
    node_states : dict[str, list[str]]
        Mapping from node name to its state labels.
    edge_strength : float
        Controls signal strength in CPDs (0.0 to 1.0).
    rng : np.random.Generator
        Random number generator.

    Returns
    -------
    list[CPD]
        One CPD per node.
    """
    cpds: list[CPD] = []

    for node_name, states in nodes:
        parents = parent_map.get(node_name, [])
        num_states = len(states)

        # Build state_names dict for this CPD
        state_names: dict[str, list[str]] = {node_name: list(states)}
        for p in parents:
            state_names[p] = list(node_states[p])

        if not parents:
            table = generate_root_cpd(num_states, rng)
        else:
            parent_cards = [len(node_states[p]) for p in parents]
            table = generate_child_cpd(num_states, parent_cards, edge_strength, rng)

        cpds.append(CPD(node=node_name, parents=parents, table=table, state_names=state_names))

    return cpds


__all__ = [
    "STATE_LABELS",
    "generate_child_cpd",
    "generate_cpds_for_dag",
    "generate_root_cpd",
]
