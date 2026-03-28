"""Case plan models: orchestrator-designed research case structure."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from sreg.models.open_investigation import SubQuestionIntent
from sreg.models.task import TaskType


class EvalQuestionPlan(BaseModel):
    """A single evaluation question planned by the orchestrator.

    Optional node hint fields let the orchestrator specify WHICH nodes the
    task should use, so that the generated question and answer reference
    the same nodes as the plan's question_text.  When hints are provided,
    the task generator respects them (after validating they exist and are
    usable); when absent, it falls back to random selection.
    """

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

    # --- Node hints (optional) ---
    # These let the orchestrator guide which nodes the task generator uses,
    # so that question_text and correct_answer describe the same entities.

    intervention_node: str | None = Field(
        default=None,
        description=(
            "Node to intervene on / treat. Used by causal_effect, "
            "adjustment_set, should_condition."
        ),
    )
    desired_state: str | None = Field(
        default=None,
        description=(
            "Target state to maximize. Used by best_intervention, "
            "compare_interventions."
        ),
    )
    compare_nodes: list[str] | None = Field(
        default=None,
        description=(
            "Two node names to compare interventions on. "
            "Used by compare_interventions."
        ),
    )
    condition_variable: str | None = Field(
        default=None,
        description=(
            "Variable suggested for conditioning. "
            "Used by should_condition."
        ),
    )

    @field_validator("compare_nodes")
    @classmethod
    def _validate_compare_nodes(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            if len(v) != 2:
                raise ValueError("compare_nodes must have exactly 2 elements")
            if v[0] == v[1]:
                raise ValueError("compare_nodes must be two distinct node names")
        return v


class CasePlan(BaseModel):
    """A research case plan designed by the orchestrator for a specific world.

    The orchestrator proposes the plan (questions, budget, rationale).
    Tools validate that questions are computable and non-degenerate.

    The research_brief is what the investigator sees — a real research
    assignment written in natural language. The questions list is the
    hidden eval agenda used for scoring.
    """

    title: str = Field(
        min_length=5,
        description="Short title for the research case",
    )
    research_context: str = Field(
        min_length=20,
        description="Narrative context explaining the research scenario",
    )
    research_brief: str = Field(
        default="",
        description=(
            "The research brief the investigator receives. Written as a real "
            "research assignment: open-ended, natural language, no variable "
            "names or eval types. This is what the agent sees as the main "
            "research question."
        ),
    )
    deliverables: list[str] = Field(
        default_factory=list,
        description=(
            "What the investigator should deliver. E.g., 'Identify the main "
            "causal factors', 'Evaluate preventive interventions'. Shown as "
            "a bullet list after the brief."
        ),
    )
    questions: list[EvalQuestionPlan] = Field(
        default_factory=list,
        description="Evaluation questions (empty in OI mode)",
    )
    shared_budget: int = Field(
        gt=0,
        description="Total observation budget shared across all questions",
    )
    rationale: str = Field(
        default="",
        description="Why this set of questions for this world",
    )

    # --- Open Investigation fields (optional) ---
    oi_sub_questions: list[SubQuestionIntent] | None = Field(
        default=None,
        description="Sub-questions for OI scoring (hidden from solver)",
    )
    # epistemic_regime removed: violated "one scoring method for everything"
    # principle. The system is general — no type-based switches.

    @property
    def primary_question(self) -> EvalQuestionPlan | None:
        """First question, or None if no questions (OI mode)."""
        return self.questions[0] if self.questions else None

    @property
    def eval_questions(self) -> list[EvalQuestionPlan]:
        """All questions after the first (alias kept for compat)."""
        return self.questions[1:]

    # Keep old name for backward compat
    @property
    def sub_questions(self) -> list[EvalQuestionPlan]:
        """All questions after the first."""
        return self.questions[1:]

    @property
    def eval_types(self) -> set[TaskType]:
        """Unique eval types in this plan."""
        return {q.eval_type for q in self.questions}

    @property
    def is_oi_mode(self) -> bool:
        """Whether this plan uses OI sub-questions instead of eval questions."""
        return self.oi_sub_questions is not None and len(self.oi_sub_questions) > 0

    @model_validator(mode="after")
    def _has_evaluation_agenda(self) -> CasePlan:
        """Must have either questions or oi_sub_questions."""
        if not self.questions and not self.oi_sub_questions:
            raise ValueError(
                "CasePlan requires either questions or oi_sub_questions"
            )
        return self

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
