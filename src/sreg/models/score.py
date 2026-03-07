"""Scoring models: functional, structural, and per-step scores."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StepScore(BaseModel):
    """Score snapshot at a single episode step."""

    step: int = Field(ge=0)
    posterior_kl: float = Field(
        ge=0.0,
        description="KL divergence between agent posterior and true posterior at this step",
    )
    cumulative_info_gain: float = Field(
        ge=0.0,
        description="Total information gained up to this step",
    )
    entropy: float = Field(
        ge=0.0,
        description="Entropy of the true posterior at this step",
    )


class Score(BaseModel):
    """Complete scoring of an agent's episode performance."""

    functional_score: float = Field(
        description="KL divergence of final answer vs true posterior (lower = better)",
    )
    information_efficiency: float = Field(
        ge=0.0,
        le=1.0,
        description="Fraction of maximum possible info gain achieved per budget unit used",
    )
    structural_score: float | None = Field(
        default=None,
        description="Secondary: SHD or edge F1 if agent proposed a causal structure",
    )
    per_step: list[StepScore] = Field(default_factory=list)
    budget_used: int = Field(ge=0)
    budget_total: int = Field(gt=0)


__all__ = ["Score", "StepScore"]
