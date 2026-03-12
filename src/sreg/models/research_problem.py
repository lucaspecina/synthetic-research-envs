"""ResearchProblem: what the agent sees — the semantic presentation of a world."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ResearchActionType(StrEnum):
    """Type of research action available to the agent."""

    OBSERVE = "observe"
    INTERVENE = "intervene"
    REQUEST_DATASET = "request_dataset"
    CONSULT = "consult"  # reserved for future use


class AvailableAction(BaseModel):
    """An action the agent can take, with semantic description and cost.

    Supports both single-node (legacy) and multi-node actions.
    Use ``nodes`` for multi-node; ``node`` is kept as backward-compatible alias.
    """

    id: str = Field(
        default="",
        description="Unique action identifier visible to the agent",
    )
    action_type: ResearchActionType = Field(
        default=ResearchActionType.OBSERVE,
        description="Type of research action",
    )
    nodes: list[str] = Field(
        default_factory=list,
        description="Node names revealed or affected by this action",
    )
    description: str = Field(
        description="Semantic description, e.g. 'Request sediment analysis'"
    )
    cost: int = Field(ge=1)

    # Backward-compat: single-node alias (= nodes[0] when len==1)
    node: str | None = Field(
        default=None,
        description="Single node name (use 'nodes' for multi-node actions)",
    )

    @model_validator(mode="after")
    def sync_node_and_nodes(self) -> AvailableAction:
        """Keep node/nodes in sync and auto-generate id if not provided."""
        if self.node and not self.nodes:
            self.nodes = [self.node]
        elif self.nodes and not self.node:
            self.node = self.nodes[0]
        elif not self.node and not self.nodes:
            raise ValueError("Either 'node' or 'nodes' must be provided")
        # Auto-generate id from nodes if not provided
        if not self.id:
            self.id = f"act_{self.nodes[0]}"
        return self


class DataAsset(BaseModel):
    """A data asset available to the agent."""

    name: str = Field(description="Name of the dataset or observation set")
    description: str = Field(description="What this data contains")
    format: str = Field(description="'tabular', 'observations', or 'narrative'")
    data: list[dict[str, str | float]] = Field(
        description="Rows of data (tabular) or list of observation dicts"
    )
    source: str | None = Field(default=None, description="Who/what generated this data")
    columns: list[str] | None = Field(default=None, description="Column names in this dataset")
    num_rows: int | None = Field(default=None, description="Number of data rows")


class ResearchProblem(BaseModel):
    """Everything the agent sees — the semantic packaging of a world + episode."""

    world_id: str
    title: str
    description: str = Field(description="Narrative context of the problem")
    domain: str
    theoretical_context: str | None = Field(
        default=None, description="Prior theories, hints, background"
    )
    data_assets: list[DataAsset] = Field(
        description="Available datasets and observations"
    )
    available_actions: list[AvailableAction] = Field(
        description="Actions the agent can take (each costs budget)"
    )
    budget: int = Field(gt=0)
    research_question: str = Field(
        description="The main question the agent must answer"
    )
    target_node: str = Field(
        description="Internal node name for evaluation"
    )
    target_states: list[str] = Field(
        description="Possible states of the target variable"
    )


__all__ = ["AvailableAction", "DataAsset", "ResearchActionType", "ResearchProblem"]
