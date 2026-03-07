"""Teacher solver output model."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sreg.models.episode import Action


class TeacherOutput(BaseModel):
    """Output from the exact Bayesian teacher solver at a single step."""

    posterior: dict[str, float] = Field(
        description="P(target_state | evidence) for each state of the target node",
    )
    recommended_action: Action | None = Field(
        default=None,
        description="Next optimal action (None if episode is complete)",
    )
    information_gain: float = Field(
        ge=0.0,
        description="Expected information gain of the recommended action",
    )
    entropy: float = Field(
        ge=0.0,
        description="Current entropy of the posterior over the target",
    )


__all__ = ["TeacherOutput"]
