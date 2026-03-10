"""Task models: task types, specifications, and task instances."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TaskType(StrEnum):
    INFER_TARGET = "infer_target"
    NEXT_BEST_OBSERVATION = "next_best_observation"
    HYPOTHESIS_SELECTION = "hypothesis_selection"
    CAUSAL_EFFECT = "causal_effect"
    BEST_INTERVENTION = "best_intervention"
    ADJUSTMENT_SET = "adjustment_set"
    COMPARE_INTERVENTIONS = "compare_interventions"


class TaskSpec(BaseModel):
    """Specification for generating a task from a world."""

    type: TaskType
    target_node: str
    max_budget: int = Field(gt=0)
    difficulty: str | None = None


class Task(BaseModel):
    """A concrete, verifiable task derived from a world."""

    id: str
    type: TaskType
    world_id: str
    question: str = Field(description="Natural language question for the agent")
    target_node: str
    available_evidence: list[str] = Field(
        description="Node names the agent can observe",
    )
    correct_answer: dict[str, float] = Field(
        description="Hidden ground truth: distribution (infer_target) or IG ranking (NBO)",
    )
    scoring_method: str = Field(
        default="kl_divergence",
        description="How to score: 'kl_divergence' or 'info_gain_ratio'",
    )
    given_evidence: dict[str, str] = Field(
        default_factory=dict,
        description="Evidence already provided to the agent (for NBO/hypothesis tasks)",
    )
    hypotheses: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Labeled hypotheses for hypothesis_selection: {label: {state: prob}}",
    )
    intervention: dict[str, str] = Field(
        default_factory=dict,
        description="Intervention for causal_effect: {node: state} (the do() operation)",
    )


class TaskBundle(BaseModel):
    """A bundle of all task types generated from the same world."""

    world_id: str
    target_node: str
    seed: int
    tasks: dict[TaskType, Task] = Field(
        description="One task per task type, all derived from the same world",
    )

    @property
    def infer_target(self) -> Task:
        return self.tasks[TaskType.INFER_TARGET]

    @property
    def next_best_observation(self) -> Task:
        return self.tasks[TaskType.NEXT_BEST_OBSERVATION]

    @property
    def hypothesis_selection(self) -> Task:
        return self.tasks[TaskType.HYPOTHESIS_SELECTION]


__all__ = ["Task", "TaskBundle", "TaskSpec", "TaskType"]
