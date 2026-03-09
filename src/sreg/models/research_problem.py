"""ResearchProblem: what the agent sees — the semantic presentation of a world."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AvailableAction(BaseModel):
    """An action the agent can take, with semantic description and cost."""

    node: str = Field(description="Internal node name for the observe action")
    description: str = Field(
        description="Semantic description, e.g. 'Request sediment analysis'"
    )
    cost: int = Field(ge=1)


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


__all__ = ["AvailableAction", "DataAsset", "ResearchProblem"]
