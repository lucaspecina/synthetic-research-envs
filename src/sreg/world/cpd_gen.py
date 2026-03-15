"""Generic CPD generation for arbitrary DAG structures.

Extracted from the three v1 templates (latent_preference, causal_chain,
fork_collider) which all use identical CPD generation logic. This module
makes that logic reusable for any DAGSpec.

Supports heterogeneous state cardinalities: each node can have a different
number of states (e.g., 2 and 3 mixed in the same world).

CPD direction: when edge directions are specified (positive/negative),
the generated CPDs respect them — "more parent = more child" (positive)
or "more parent = less child" (negative). Without direction, falls back
to a neutral monotone (identity mapping) instead of random permutation.
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
    parent_directions: list[str | None] | None = None,
) -> list[list[float]]:
    """CPD for a child node given its parents, with optional direction.

    Uses a signed ordinal scoring model: each parent contributes a signed
    score based on its state position and edge direction. The scores are
    summed across parents, mapped to a child center state, and used to
    generate a Dirichlet distribution peaked at that center.

    Parameters
    ----------
    num_child_states : int
        Number of states of the child node.
    parent_cards : list[int]
        Cardinality (number of states) of each parent, in order.
    edge_strength : float
        Controls how peaked CPDs are. 0.0 = near-uniform, 1.0 = very peaked.
    rng : np.random.Generator
        Random number generator.
    parent_directions : list[str | None] | None
        Direction of effect for each parent edge:
        - "positive": more parent = more child (identity mapping)
        - "negative": more parent = less child (reverse mapping)
        - None: neutral monotone (identity, with slight noise)
        If None (the whole list), defaults to neutral for all parents.

    Returns
    -------
    list[list[float]]
        CPD table: rows = child states, cols = parent state combinations.
    """
    num_combos = 1
    for c in parent_cards:
        num_combos *= c

    # Resolve directions
    if parent_directions is None:
        parent_directions = [None] * len(parent_cards)

    # Direction signs: +1 for positive/neutral, -1 for negative
    signs = []
    for d in parent_directions:
        if d == "negative":
            signs.append(-1.0)
        else:
            signs.append(1.0)

    table = np.zeros((num_child_states, num_combos))

    for col_idx in range(num_combos):
        # Decode parent state indices (first parent varies slowest)
        parent_indices: list[int] = []
        temp = col_idx
        for card in reversed(parent_cards):
            parent_indices.insert(0, temp % card)
            temp //= card

        # Compute signed ordinal score for each parent
        # Each parent contributes: sign * normalized_position * strength
        total_score = 0.0
        total_weight = 0.0
        for p_idx, p_state in enumerate(parent_indices):
            p_card = parent_cards[p_idx]
            # Normalize parent state to [-1, +1]
            if p_card > 1:
                normalized = (p_state / (p_card - 1)) * 2.0 - 1.0  # -1 to +1
            else:
                normalized = 0.0
            contribution = signs[p_idx] * normalized * edge_strength
            total_score += contribution
            total_weight += edge_strength

        # Map total score to child center state
        # total_score ranges from roughly -edge_strength*num_parents to +edge_strength*num_parents
        # Normalize to [0, num_child_states - 1]
        if total_weight > 0:
            norm_score = total_score / total_weight  # -1 to +1
        else:
            norm_score = 0.0
        center = (norm_score + 1.0) / 2.0 * (num_child_states - 1)  # 0 to num_child_states-1
        center = max(0.0, min(float(num_child_states - 1), center))
        dominant = int(round(center))

        # Generate Dirichlet distribution peaked at dominant state
        base = max(0.1, (1.0 - edge_strength) * 2.0)
        alpha = np.full(num_child_states, base)
        alpha[dominant] += edge_strength * 15.0

        # Add slight noise to neighboring states for more natural distributions
        if num_child_states > 2:
            frac = center - int(center)
            if dominant + 1 < num_child_states and frac > 0.3:
                alpha[dominant + 1] += edge_strength * 5.0 * frac
            if dominant - 1 >= 0 and frac < -0.3:
                alpha[dominant - 1] += edge_strength * 5.0 * abs(frac)

        probs = rng.dirichlet(alpha)
        table[:, col_idx] = probs

    return table.tolist()


def generate_cpds_for_dag(
    nodes: list[tuple[str, list[str]]],
    parent_map: dict[str, list[str]],
    node_states: dict[str, list[str]],
    edge_strength: float,
    rng: np.random.Generator,
    edge_directions: dict[tuple[str, str], str] | None = None,
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
    edge_directions : dict[tuple[str, str], str] | None
        Optional mapping from (parent, child) edge to direction:
        "positive" or "negative". Edges not in the dict default to
        neutral (identity) mapping.

    Returns
    -------
    list[CPD]
        One CPD per node.
    """
    cpds: list[CPD] = []
    dirs = edge_directions or {}

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
            # Look up direction for each parent edge
            parent_dirs = [dirs.get((p, node_name)) for p in parents]
            table = generate_child_cpd(
                num_states, parent_cards, edge_strength, rng,
                parent_directions=parent_dirs,
            )

        cpds.append(CPD(node=node_name, parents=parents, table=table, state_names=state_names))

    return cpds


__all__ = [
    "STATE_LABELS",
    "generate_child_cpd",
    "generate_cpds_for_dag",
    "generate_root_cpd",
]
