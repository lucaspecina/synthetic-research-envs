"""RL environment protocol for SREG.

Defines the interface that wraps SREG as a training environment
for RL frameworks (verifiers/prime-rl). Inspired by Gymnasium
and verifiers MultiTurnEnv, but using structured actions/observations.

The actual implementation will adapt EpisodeRunner + ProblemBuilder
into this interface.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


class EnvAction(BaseModel):
    """Structured action from the agent (not a raw string)."""

    tool_name: str  # "research_action", "python_exec", "submit"
    arguments: dict[str, Any] = Field(default_factory=dict)


class EnvObservation(BaseModel):
    """Structured observation returned to the agent."""

    text: str  # human-readable observation for the LLM
    available_tools: list[str] = Field(default_factory=list)
    step_index: int = 0
    budget_remaining: int | None = None


class EnvStepResult(BaseModel):
    """Result of taking one step in the environment."""

    observation: EnvObservation
    reward: float = 0.0
    terminated: bool = False  # episode ended normally (submit or budget exhausted)
    truncated: bool = False  # episode cut short (max steps, error)
    info: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Environment protocol
# ---------------------------------------------------------------------------


class SREGEnvironment(Protocol):
    """Protocol for SREG as an RL training environment.

    Adapts EpisodeRunner + ResearchProblem + VerifierTool into
    a standard reset/step interface for verifiers MultiTurnEnv.

    Each episode = one SRC (research case). The agent uses tools
    (research_action, python_exec, submit) and receives observations.
    Reward is computed at termination from the BN ground truth.
    """

    def reset(self, seed: int | None = None) -> EnvObservation:
        """Generate a new SRC and return the initial observation.

        The observation contains the problem description, data,
        available actions, and research question.
        """
        ...

    def step(self, action: EnvAction) -> EnvStepResult:
        """Process one agent action and return the result.

        Actions: research_action, python_exec, submit.
        Reward is 0.0 for non-terminal steps, computed at termination.
        """
        ...
