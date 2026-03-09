"""DAGSpec: universal contract for arbitrary DAG structures.

A DAGSpec describes the structure of a Bayesian network (nodes + edges)
without CPDs. It is the input to CustomTemplate, which generates CPDs
and produces a World.

Any source (manual, motif composer, DAG generators, LLM extractor)
produces a DAGSpec that enters the same pipeline.
"""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, Field, model_validator

from sreg.models.world import NodeType

MAX_PARENTS = 4


class DAGNodeSpec(BaseModel):
    """Specification for a single node in a DAG."""

    name: str = Field(description="Variable name, e.g. 'water_temperature'")
    type: NodeType
    states: list[str] = Field(
        min_length=2,
        description="Possible values, e.g. ['low', 'medium', 'high']",
    )
    role: str | None = Field(
        default=None,
        description="Semantic role metadata: 'driver', 'proxy', 'confounder', etc. "
        "Free-form string, does not affect generation.",
    )


class DAGSpec(BaseModel):
    """Universal contract for an arbitrary DAG structure.

    Validates:
    - Graph is acyclic (DAG)
    - At least one TARGET node
    - At least one OBSERVABLE node
    - All nodes referenced in edges exist
    - No duplicate node names
    - Max parents per node <= MAX_PARENTS (default 4)
    """

    nodes: list[DAGNodeSpec] = Field(min_length=2)
    edges: list[tuple[str, str]] = Field(
        description="Directed edges as (from_node, to_node) pairs",
    )

    @model_validator(mode="after")
    def validate_no_duplicate_names(self) -> DAGSpec:
        names = [n.name for n in self.nodes]
        dupes = [name for name in names if names.count(name) > 1]
        if dupes:
            raise ValueError(f"Duplicate node names: {set(dupes)}")
        return self

    @model_validator(mode="after")
    def validate_edge_references(self) -> DAGSpec:
        node_names = {n.name for n in self.nodes}
        for src, dst in self.edges:
            if src not in node_names:
                raise ValueError(f"Edge references unknown node '{src}'")
            if dst not in node_names:
                raise ValueError(f"Edge references unknown node '{dst}'")
        return self

    @model_validator(mode="after")
    def validate_has_target(self) -> DAGSpec:
        if not any(n.type == NodeType.TARGET for n in self.nodes):
            raise ValueError("DAGSpec must have at least one TARGET node")
        return self

    @model_validator(mode="after")
    def validate_has_observable(self) -> DAGSpec:
        if not any(n.type == NodeType.OBSERVABLE for n in self.nodes):
            raise ValueError("DAGSpec must have at least one OBSERVABLE node")
        return self

    @model_validator(mode="after")
    def validate_is_dag(self) -> DAGSpec:
        g = nx.DiGraph()
        g.add_nodes_from(n.name for n in self.nodes)
        g.add_edges_from(self.edges)
        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("Graph contains cycles — must be a DAG")
        return self

    @model_validator(mode="after")
    def validate_max_parents(self) -> DAGSpec:
        parent_count: dict[str, int] = {n.name: 0 for n in self.nodes}
        for _, dst in self.edges:
            parent_count[dst] += 1
        violations = {name: cnt for name, cnt in parent_count.items() if cnt > MAX_PARENTS}
        if violations:
            raise ValueError(
                f"Nodes exceed max parents ({MAX_PARENTS}): "
                f"{', '.join(f'{n}={c}' for n, c in violations.items())}"
            )
        return self

    # --- Convenience methods ---

    def node_names(self) -> list[str]:
        """All node names in order."""
        return [n.name for n in self.nodes]

    def get_node(self, name: str) -> DAGNodeSpec:
        """Get node spec by name."""
        for n in self.nodes:
            if n.name == name:
                return n
        raise KeyError(f"Node '{name}' not found")

    def parents_of(self, name: str) -> list[str]:
        """Get parent node names for a given node."""
        return [src for src, dst in self.edges if dst == name]

    def children_of(self, name: str) -> list[str]:
        """Get child node names for a given node."""
        return [dst for src, dst in self.edges if src == name]

    def to_networkx(self) -> nx.DiGraph:
        """Convert to a networkx DiGraph."""
        g = nx.DiGraph()
        g.add_nodes_from(n.name for n in self.nodes)
        g.add_edges_from(self.edges)
        return g

    def nodes_by_type(self, node_type: NodeType) -> list[DAGNodeSpec]:
        """Get all nodes of a given type."""
        return [n for n in self.nodes if n.type == node_type]


__all__ = ["DAGNodeSpec", "DAGSpec", "MAX_PARENTS"]
