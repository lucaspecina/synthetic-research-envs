"""DAG generators: produce valid DAGSpecs with different topological properties.

Four methods inspired by Reasoning Core (Sileo et al. 2026), all guaranteeing
acyclicity by construction via topological ordering (edges only go from lower
to higher index).

Each generator takes structural parameters and produces a DAGSpec ready for
CustomTemplate. Node types (LATENT/OBSERVABLE/TARGET) and state cardinalities
are assigned automatically based on parameters.

Usage:
    from sreg.world.dag_generators import generate_erdos_renyi, generate_layered

    spec = generate_erdos_renyi(num_nodes=12, num_latent=2, edge_prob=0.3, seed=42)
    spec = generate_layered(num_layers=4, nodes_per_layer=3, seed=42)
"""

from __future__ import annotations

import numpy as np

from sreg.models.dag_spec import MAX_PARENTS, DAGNodeSpec, DAGSpec
from sreg.models.world import NodeType
from sreg.world.cpd_gen import STATE_LABELS


def _assign_node_types(
    num_nodes: int,
    num_latent: int,
    num_target: int,
    rng: np.random.Generator,
) -> list[NodeType]:
    """Assign LATENT/OBSERVABLE/TARGET types to node indices.

    Latents are placed among the first ~60% of nodes (topologically early,
    so they can influence downstream nodes). Targets are placed among the
    last ~40%. Remaining nodes are OBSERVABLE.
    """
    types = [NodeType.OBSERVABLE] * num_nodes

    # Place latents in early positions
    early_cutoff = max(num_latent, int(num_nodes * 0.6))
    early_indices = list(range(early_cutoff))
    rng.shuffle(early_indices)
    for i in range(num_latent):
        types[early_indices[i]] = NodeType.LATENT

    # Place targets in late positions (avoid overlap with latents)
    late_indices = [i for i in range(num_nodes) if types[i] != NodeType.LATENT]
    # Prefer later positions for targets
    late_indices = sorted(late_indices, reverse=True)
    for i in range(num_target):
        types[late_indices[i]] = NodeType.TARGET

    return types


def _assign_states(
    num_nodes: int,
    num_states: int | list[int],
    rng: np.random.Generator,
) -> list[list[str]]:
    """Assign state labels to each node.

    If num_states is an int, all nodes get that many states.
    If num_states is a list, each node gets states sampled from that list.
    """
    if isinstance(num_states, int):
        return [list(STATE_LABELS[num_states])] * num_nodes

    # Sample from the list for each node
    all_states = []
    for _ in range(num_nodes):
        ns = rng.choice(num_states)
        all_states.append(list(STATE_LABELS[ns]))
    return all_states


def _cap_parents(edges: list[tuple[int, int]], max_parents: int) -> list[tuple[int, int]]:
    """Remove edges that would exceed max_parents for any node."""
    parent_count: dict[int, int] = {}
    kept: list[tuple[int, int]] = []
    for src, dst in edges:
        count = parent_count.get(dst, 0)
        if count < max_parents:
            kept.append((src, dst))
            parent_count[dst] = count + 1
    return kept


def generate_erdos_renyi(
    *,
    num_nodes: int = 10,
    num_latent: int = 1,
    num_target: int = 1,
    num_states: int | list[int] = 3,
    edge_prob: float = 0.3,
    seed: int = 42,
) -> DAGSpec:
    """Erdos-Renyi DAG: each possible edge included with probability `edge_prob`.

    Acyclicity guaranteed by topological ordering (edges only go i -> j where i < j).
    Good for: random DAGs for testing, exploring the space broadly.

    Parameters
    ----------
    num_nodes : int
        Total number of nodes.
    num_latent : int
        Number of LATENT nodes.
    num_target : int
        Number of TARGET nodes.
    num_states : int or list[int]
        States per node. Int for uniform, list to sample from (e.g., [2, 3]).
    edge_prob : float
        Probability of each edge existing (0.0 to 1.0).
    seed : int
        Random seed.
    """
    rng = np.random.default_rng(seed)

    # Generate edges: upper triangular (i < j guarantees acyclicity)
    edges = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if rng.random() < edge_prob:
                edges.append((i, j))

    edges = _cap_parents(edges, MAX_PARENTS)

    types = _assign_node_types(num_nodes, num_latent, num_target, rng)
    states = _assign_states(num_nodes, num_states, rng)

    nodes = [
        DAGNodeSpec(name=f"v{i}", type=types[i], states=states[i])
        for i in range(num_nodes)
    ]
    named_edges = [(f"v{i}", f"v{j}") for i, j in edges]

    return DAGSpec(nodes=nodes, edges=named_edges)


def generate_spanning_tree(
    *,
    num_nodes: int = 10,
    num_latent: int = 1,
    num_target: int = 1,
    num_states: int | list[int] = 3,
    extra_edge_prob: float = 0.1,
    seed: int = 42,
) -> DAGSpec:
    """Spanning tree DAG: tree first, then extra edges with probability.

    Guarantees a connected graph (every node reachable from root). Extra edges
    add density and create more complex structures (colliders, multiple paths).
    Good for: connected DAGs with controlled density.

    Parameters
    ----------
    num_nodes : int
        Total number of nodes.
    num_latent : int
        Number of LATENT nodes.
    num_target : int
        Number of TARGET nodes.
    num_states : int or list[int]
        States per node.
    extra_edge_prob : float
        Probability of adding non-tree edges (0.0 = pure tree).
    seed : int
        Random seed.
    """
    rng = np.random.default_rng(seed)

    # Build a random spanning tree: each node (except 0) picks a random parent
    # from earlier nodes
    tree_edges: list[tuple[int, int]] = []
    for j in range(1, num_nodes):
        parent = rng.integers(0, j)
        tree_edges.append((int(parent), j))

    # Add extra edges (upper triangular, skip existing tree edges)
    tree_set = set(tree_edges)
    extra_edges: list[tuple[int, int]] = []
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if (i, j) not in tree_set and rng.random() < extra_edge_prob:
                extra_edges.append((i, j))

    all_edges = tree_edges + extra_edges
    all_edges = _cap_parents(all_edges, MAX_PARENTS)

    types = _assign_node_types(num_nodes, num_latent, num_target, rng)
    states = _assign_states(num_nodes, num_states, rng)

    nodes = [
        DAGNodeSpec(name=f"v{i}", type=types[i], states=states[i])
        for i in range(num_nodes)
    ]
    named_edges = [(f"v{i}", f"v{j}") for i, j in all_edges]

    return DAGSpec(nodes=nodes, edges=named_edges)


def generate_preferential_attachment(
    *,
    num_nodes: int = 10,
    num_latent: int = 1,
    num_target: int = 1,
    num_states: int | list[int] = 3,
    num_edges_per_node: int = 2,
    seed: int = 42,
) -> DAGSpec:
    """Preferential attachment DAG: nodes with more edges attract more.

    Produces hub-like structures similar to latent_preference (a few highly
    connected nodes, many leaf nodes). Natural for causal systems where
    a few root causes drive many effects.
    Good for: star-like structures, hub-and-spoke, scale-free-ish DAGs.

    Parameters
    ----------
    num_nodes : int
        Total number of nodes.
    num_latent : int
        Number of LATENT nodes.
    num_target : int
        Number of TARGET nodes.
    num_states : int or list[int]
        States per node.
    num_edges_per_node : int
        How many edges each new node tries to create to earlier nodes.
    seed : int
        Random seed.
    """
    rng = np.random.default_rng(seed)

    edges: list[tuple[int, int]] = []
    # degree[i] tracks how many edges node i participates in (for preferential attachment)
    degree = np.ones(num_nodes, dtype=float)  # start with 1 to avoid zero probs

    for j in range(1, num_nodes):
        # Available parents: all earlier nodes
        candidates = list(range(j))
        probs = degree[:j].copy()
        probs /= probs.sum()

        # Pick up to num_edges_per_node parents (without replacement)
        k = min(num_edges_per_node, len(candidates), MAX_PARENTS)
        parents = rng.choice(candidates, size=k, replace=False, p=probs)

        for parent in parents:
            edges.append((int(parent), j))
            degree[parent] += 1
            degree[j] += 1

    edges = _cap_parents(edges, MAX_PARENTS)

    types = _assign_node_types(num_nodes, num_latent, num_target, rng)
    states = _assign_states(num_nodes, num_states, rng)

    nodes = [
        DAGNodeSpec(name=f"v{i}", type=types[i], states=states[i])
        for i in range(num_nodes)
    ]
    named_edges = [(f"v{i}", f"v{j}") for i, j in edges]

    return DAGSpec(nodes=nodes, edges=named_edges)


def generate_layered(
    *,
    num_layers: int = 4,
    nodes_per_layer: int | list[int] = 3,
    num_latent: int = 1,
    num_target: int = 1,
    num_states: int | list[int] = 3,
    inter_layer_prob: float = 0.5,
    skip_layer_prob: float = 0.1,
    seed: int = 42,
) -> DAGSpec:
    """Layered DAG: nodes organized in layers, edges go forward between layers.

    Produces pipeline/stage-like structures. First layer tends to be causes,
    last layer tends to be effects. Skip connections add complexity.
    Good for: staged processes, pipelines, temporal-like structures.

    Parameters
    ----------
    num_layers : int
        Number of layers.
    nodes_per_layer : int or list[int]
        Nodes per layer. Int for uniform, list for per-layer specification.
    num_latent : int
        Number of LATENT nodes.
    num_target : int
        Number of TARGET nodes.
    num_states : int or list[int]
        States per node.
    inter_layer_prob : float
        Probability of edge between adjacent layers.
    skip_layer_prob : float
        Probability of edge skipping one layer.
    seed : int
        Random seed.
    """
    rng = np.random.default_rng(seed)

    # Determine nodes per layer
    if isinstance(nodes_per_layer, int):
        layer_sizes = [nodes_per_layer] * num_layers
    else:
        layer_sizes = list(nodes_per_layer)
        while len(layer_sizes) < num_layers:
            layer_sizes.append(layer_sizes[-1])

    # Build layers: list of node indices per layer
    layers: list[list[int]] = []
    idx = 0
    for size in layer_sizes:
        layers.append(list(range(idx, idx + size)))
        idx += size
    num_nodes = idx

    # Generate edges between layers
    edges: list[tuple[int, int]] = []
    for layer_idx in range(len(layers)):
        src_layer = layers[layer_idx]

        # Adjacent layer
        if layer_idx + 1 < len(layers):
            dst_layer = layers[layer_idx + 1]
            for s in src_layer:
                for d in dst_layer:
                    if rng.random() < inter_layer_prob:
                        edges.append((s, d))

        # Skip layer
        if layer_idx + 2 < len(layers):
            skip_layer = layers[layer_idx + 2]
            for s in src_layer:
                for d in skip_layer:
                    if rng.random() < skip_layer_prob:
                        edges.append((s, d))

    # Ensure every non-root node has at least one parent (connectivity)
    nodes_with_parents = {dst for _, dst in edges}
    for layer_idx in range(1, len(layers)):
        for node in layers[layer_idx]:
            if node not in nodes_with_parents:
                # Connect to a random node in the previous layer
                parent = rng.choice(layers[layer_idx - 1])
                edges.append((int(parent), node))

    edges = _cap_parents(edges, MAX_PARENTS)

    types = _assign_node_types(num_nodes, num_latent, num_target, rng)
    states = _assign_states(num_nodes, num_states, rng)

    nodes = [
        DAGNodeSpec(name=f"v{i}", type=types[i], states=states[i])
        for i in range(num_nodes)
    ]
    named_edges = [(f"v{i}", f"v{j}") for i, j in edges]

    return DAGSpec(nodes=nodes, edges=named_edges)


__all__ = [
    "generate_erdos_renyi",
    "generate_layered",
    "generate_preferential_attachment",
    "generate_spanning_tree",
]
