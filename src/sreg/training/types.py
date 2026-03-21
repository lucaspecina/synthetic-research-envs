"""Types for the training integration layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvalType = Literal[
    "infer_target",
    "causal_effect",
    "hypothesis_selection",
    "next_best_observation",
    "best_intervention",
    "adjustment_set",
    "compare_interventions",
    "should_condition",
    "infer_latent_cause",
    "ate",
    "mediation",
    "interaction",
]

# Eval types that expect a probability distribution as answer
DISTRIBUTION_EVAL_TYPES: set[str] = {
    "infer_target",
    "causal_effect",
    "infer_latent_cause",
}

# Eval types that expect a single choice (string) as answer
CHOICE_EVAL_TYPES: set[str] = {
    "hypothesis_selection",
    "next_best_observation",
    "best_intervention",
    "compare_interventions",
    "should_condition",
    "interaction",
}

# Eval types that expect a single numeric value as answer
NUMERIC_EVAL_TYPES: set[str] = {
    "ate",
    "mediation",
}

# Eval types that expect a set of variable names
SET_EVAL_TYPES: set[str] = {
    "adjustment_set",
}


class SubmitPayload(BaseModel):
    """Agent's submission — exactly one field must be populated."""

    choice: str | None = Field(
        default=None,
        description="Single choice answer (hypothesis label, variable name, A/B, yes/no)",
    )
    distribution: dict[str, float] | None = Field(
        default=None,
        description="Probability distribution over target states, e.g. {'low': 0.3, 'high': 0.7}",
    )
    adjustment_set: list[str] | None = Field(
        default=None,
        description="Set of variable names to condition on",
    )
    value: float | None = Field(
        default=None,
        description="Numeric answer (ATE estimate, fraction mediated)",
    )
