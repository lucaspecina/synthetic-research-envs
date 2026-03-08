"""World model: DAG structure, nodes, edges, and conditional probability distributions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class NodeType(StrEnum):
    OBSERVABLE = "observable"
    LATENT = "latent"
    TARGET = "target"


class Node(BaseModel):
    """A variable in the world's causal graph."""

    name: str = Field(description="Semantic name, e.g. 'thermal_flux'")
    type: NodeType
    description: str = Field(description="LLM-generated description of this variable")
    states: list[str] = Field(
        min_length=2,
        description="Possible values, e.g. ['low', 'medium', 'high']",
    )


class Edge(BaseModel):
    """A directed causal link between two nodes."""

    from_node: str
    to_node: str
    mechanism: str = Field(description="LLM-generated description of the causal mechanism")


class CPD(BaseModel):
    """Conditional probability distribution for a node given its parents.

    The table is stored as a 2D list: rows = node states, columns = parent state combinations.
    Parent state combinations follow lexicographic order over parents (left parent varies slowest).
    For root nodes (no parents), the table has a single column.
    """

    node: str
    parents: list[str] = Field(default_factory=list)
    table: list[list[float]] = Field(
        description="P(node_state | parent_states). Shape: num_states x parent_combos",
    )
    state_names: dict[str, list[str]] = Field(
        description="Mapping from node/parent names to their state lists",
    )

    @model_validator(mode="after")
    def validate_table_shape(self) -> CPD:
        node_states = self.state_names.get(self.node, [])
        if len(self.table) != len(node_states):
            raise ValueError(
                f"Table has {len(self.table)} rows but node '{self.node}' "
                f"has {len(node_states)} states"
            )

        expected_cols = 1
        for parent in self.parents:
            parent_states = self.state_names.get(parent, [])
            if not parent_states:
                raise ValueError(f"Parent '{parent}' not found in state_names")
            expected_cols *= len(parent_states)

        for i, row in enumerate(self.table):
            if len(row) != expected_cols:
                raise ValueError(f"Row {i} has {len(row)} columns but expected {expected_cols}")

        return self

    @model_validator(mode="after")
    def validate_probabilities_sum_to_one(self) -> CPD:
        num_cols = len(self.table[0]) if self.table else 0
        for col_idx in range(num_cols):
            col_sum = sum(row[col_idx] for row in self.table)
            if abs(col_sum - 1.0) > 1e-6:
                raise ValueError(f"Column {col_idx} sums to {col_sum}, expected 1.0")
        return self


class DifficultyProfile(BaseModel):
    """Characterizes the difficulty of a world."""

    level: str = Field(description="Difficulty level: 'easy', 'medium', 'hard'")
    num_nodes: int = Field(ge=2)
    num_latent: int = Field(ge=0)
    num_observable: int = Field(ge=1)
    edge_density: float = Field(ge=0.0, le=1.0, description="edges / max_possible_edges")
    avg_states_per_node: float = Field(gt=0.0)
    posterior_entropy: float | None = Field(
        default=None,
        description="Entropy of target posterior given no evidence (computed after generation)",
    )


class World(BaseModel):
    """A complete synthetic world: causal DAG with probability distributions."""

    id: str
    seed: int
    template_family: str
    description: str = Field(description="LLM-generated world description")
    nodes: list[Node] = Field(min_length=2)
    edges: list[Edge]
    cpds: list[CPD]
    difficulty: DifficultyProfile

    # Semantic layer (Phase 6) — optional for backwards compatibility
    scenario_title: str | None = Field(
        default=None, description="Title of the research problem"
    )
    scenario_description: str | None = Field(
        default=None, description="Narrative context (2-3 paragraphs)"
    )
    domain: str | None = Field(
        default=None, description="Scientific domain (ecology, epidemiology, etc.)"
    )
    theoretical_context: str | None = Field(
        default=None, description="Prior theories, hints, partial findings"
    )

    @model_validator(mode="after")
    def validate_node_references(self) -> World:
        node_names = {n.name for n in self.nodes}
        for edge in self.edges:
            if edge.from_node not in node_names:
                raise ValueError(f"Edge references unknown node '{edge.from_node}'")
            if edge.to_node not in node_names:
                raise ValueError(f"Edge references unknown node '{edge.to_node}'")
        for cpd in self.cpds:
            if cpd.node not in node_names:
                raise ValueError(f"CPD references unknown node '{cpd.node}'")
            for parent in cpd.parents:
                if parent not in node_names:
                    raise ValueError(f"CPD parent references unknown node '{parent}'")
        return self

    @model_validator(mode="after")
    def validate_has_target(self) -> World:
        targets = [n for n in self.nodes if n.type == NodeType.TARGET]
        if not targets:
            raise ValueError("World must have at least one target node")
        return self

    @model_validator(mode="after")
    def validate_cpd_coverage(self) -> World:
        node_names = {n.name for n in self.nodes}
        cpd_nodes = {cpd.node for cpd in self.cpds}
        missing = node_names - cpd_nodes
        if missing:
            raise ValueError(f"Nodes without CPDs: {missing}")
        return self


__all__ = ["CPD", "DifficultyProfile", "Edge", "Node", "NodeType", "World"]
