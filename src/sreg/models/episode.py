"""Episode models: actions, observations, and step results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ActionType(StrEnum):
    OBSERVE = "observe"
    INTERVENE = "intervene"
    SUBMIT = "submit"
    QUERY_DISTRIBUTION = "query_distribution"


class ActionDef(BaseModel):
    """Formal definition of an available action in the episode.

    Maps an action ID to its type, the nodes it reveals, and its cost.
    Used by EpisodeRunner to process multi-node and typed actions.
    """

    id: str = Field(description="Unique action identifier, e.g. 'observe_water_temp'")
    action_type: str = Field(
        default="observe",
        description="Type: 'observe', 'intervene', 'request_dataset'",
    )
    nodes: list[str] = Field(min_length=1, description="Nodes revealed or affected by this action")
    cost: int = Field(ge=1, description="Budget cost of this action")
    effects: dict[str, str] = Field(
        default_factory=dict,
        description="For intervene actions: node -> state to set, e.g. {'water_temp': 'high'}",
    )


class Action(BaseModel):
    """An action taken by an agent during an episode."""

    type: ActionType
    node: str | None = Field(
        default=None,
        description="Target node for observe/query_distribution actions",
    )
    action_id: str | None = Field(
        default=None,
        description="Action definition ID for compound/typed actions",
    )
    answer: dict[str, float] | None = Field(
        default=None,
        description="For submit: probability distribution over target states",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="For submit: agent's self-reported confidence",
    )

    @model_validator(mode="after")
    def validate_action_fields(self) -> Action:
        if self.type in (ActionType.OBSERVE, ActionType.INTERVENE, ActionType.QUERY_DISTRIBUTION):
            if self.node is None and self.action_id is None:
                raise ValueError(
                    f"Action '{self.type}' requires a 'node' or 'action_id'"
                )
        if self.type == ActionType.SUBMIT:
            if self.answer is None:
                raise ValueError("Submit action requires an 'answer'")
        return self


class Observation(BaseModel):
    """An observation returned by the environment after an observe action."""

    node: str
    state: str = Field(description="Observed discrete state, e.g. 'high'")
    value: float | None = Field(
        default=None,
        description="Optional numeric value associated with the state",
    )
    description: str = Field(
        description="Natural language, e.g. 'thermal_flux was observed to be HIGH (value: 0.84)'",
    )


class StepResult(BaseModel):
    """Result of a single step in an episode."""

    step: int = Field(ge=0)
    action: Action
    observation: Observation | None = Field(
        default=None,
        description="Observation returned (None for submit/query actions)",
    )
    extra_observations: list[Observation] = Field(
        default_factory=list,
        description="Additional observations from multi-node actions",
    )
    distribution: dict[str, float] | None = Field(
        default=None,
        description="Distribution returned for query_distribution actions",
    )
    remaining_budget: int = Field(ge=0)


class Episode(BaseModel):
    """A complete interaction episode within a world."""

    id: str
    world_id: str
    budget: int = Field(gt=0, description="Total observation budget")
    initial_evidence: list[Observation] = Field(
        default_factory=list,
        description="Evidence provided to the agent at the start",
    )
    available_nodes: list[str] = Field(
        min_length=1,
        description="Nodes the agent can choose to observe",
    )
    node_costs: dict[str, int] = Field(
        description="Cost to observe each available node",
    )
    action_defs: list[ActionDef] = Field(
        default_factory=list,
        description="Rich action definitions. Empty = legacy mode (use available_nodes/node_costs)",
    )
    steps: list[StepResult] = Field(default_factory=list)


__all__ = ["Action", "ActionDef", "ActionType", "Episode", "Observation", "StepResult"]
