"""Case plan models: orchestrator-designed research case structure."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from sreg.models.task import TaskType


class EvalQuestionPlan(BaseModel):
    """A single evaluation question planned by the orchestrator."""

    question_text: str = Field(
        min_length=10,
        description="Natural language question, e.g. 'What is the most likely soil type?'",
    )
    eval_type: TaskType = Field(
        description="Evaluation type: infer_target, next_best_observation, hypothesis_selection",
    )
    target_node: str = Field(
        description="Which node this question evaluates (must exist in the world)",
    )
    rationale: str = Field(
        default="",
        description="Why this question matters for this research case",
    )


class CasePlan(BaseModel):
    """A research case plan designed by the orchestrator for a specific world.

    The orchestrator proposes the plan (questions, budget, rationale).
    Tools validate that questions are computable and non-degenerate.
    """

    title: str = Field(
        min_length=5,
        description="Short title for the research case",
    )
    research_context: str = Field(
        min_length=20,
        description="Narrative context explaining the research scenario",
    )
    questions: list[EvalQuestionPlan] = Field(
        min_length=1,
        description="Evaluation questions (at least one required)",
    )
    shared_budget: int = Field(
        gt=0,
        description="Total observation budget shared across all questions",
    )
    rationale: str = Field(
        default="",
        description="Why this set of questions for this world",
    )

    @property
    def primary_question(self) -> EvalQuestionPlan:
        """First question is always the primary one."""
        return self.questions[0]

    @property
    def sub_questions(self) -> list[EvalQuestionPlan]:
        """All questions after the first."""
        return self.questions[1:]

    @property
    def eval_types(self) -> set[TaskType]:
        """Unique eval types in this plan."""
        return {q.eval_type for q in self.questions}

    @model_validator(mode="after")
    def _no_duplicate_questions(self) -> CasePlan:
        """No two questions should have the same eval_type + target_node."""
        seen = set()
        for q in self.questions:
            key = (q.eval_type, q.target_node)
            if key in seen:
                raise ValueError(
                    f"Duplicate question: eval_type={q.eval_type}, "
                    f"target_node={q.target_node}"
                )
            seen.add(key)
        return self


__all__ = ["CasePlan", "EvalQuestionPlan"]
