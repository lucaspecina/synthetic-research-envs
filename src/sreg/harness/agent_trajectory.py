"""Agent trajectory extraction and export.

Extracts structured, inspectable trajectories from AgentResult by
post-processing the raw chat messages. No changes to AgentSolver needed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from sreg.agent.agent import AgentResult
from sreg.models.research_problem import ResearchProblem


class AgentTrajectoryStep(BaseModel):
    """A single step in the agent's trajectory."""

    step: int
    thinking: str | None = None
    tool_call: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None
    observation: str | None = None
    error: str | None = None
    is_submit: bool = False


class AgentTrajectory(BaseModel):
    """Complete structured trajectory from an agent run."""

    world_id: str
    seed: int
    target_node: str
    target_states: list[str]
    budget: int
    budget_used: int
    steps: list[AgentTrajectoryStep]
    submitted_answer: Any = None  # dict, str, list — depends on task type
    reasoning: str | None = None
    confidence: float | None = None
    score: float | None = None
    task_type: str | None = None


def extract_agent_trajectory(
    result: AgentResult,
    problem: ResearchProblem,
    world_id: str = "",
    seed: int = 0,
) -> AgentTrajectory:
    """Extract a structured trajectory from an AgentResult's messages.

    Walks the raw chat messages list, pairs assistant tool_calls with
    their tool responses, and builds AgentTrajectoryStep objects.

    Args:
        result: The AgentResult from AgentSolver.solve().
        problem: The ResearchProblem (for metadata).
        world_id: World identifier.
        seed: Seed used for the run.

    Returns:
        An AgentTrajectory with one step per tool call.
    """
    steps: list[AgentTrajectoryStep] = []
    messages = result.messages

    # Build a map: tool_call_id -> tool response content
    tool_responses: dict[str, dict] = {}
    for msg in messages:
        if msg.get("role") == "tool":
            tc_id = msg.get("tool_call_id", "")
            content = msg.get("content", "{}")
            try:
                tool_responses[tc_id] = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                tool_responses[tc_id] = {"raw": content}

    step_num = 0
    for msg in messages:
        if msg.get("role") != "assistant":
            continue

        thinking = msg.get("content")
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            # Assistant message with no tool calls (final text or thinking-only)
            if thinking:
                steps.append(AgentTrajectoryStep(
                    step=step_num,
                    thinking=thinking,
                ))
                step_num += 1
            continue

        for tc in tool_calls:
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            try:
                fn_args = json.loads(fn.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError):
                fn_args = {"raw": fn.get("arguments", "")}

            tc_id = tc.get("id", "")
            tc_result = tool_responses.get(tc_id, {})

            observation = None
            error = None
            is_submit = False

            if "error" in tc_result:
                error = tc_result["error"]
            elif fn_name == "observe":
                var = tc_result.get("variable", fn_args.get("variable", "?"))
                state = tc_result.get("observed_state", "?")
                observation = f"{var} = {state}"
            elif fn_name == "submit":
                is_submit = True

            steps.append(AgentTrajectoryStep(
                step=step_num,
                thinking=thinking,
                tool_call=fn_name,
                tool_args=fn_args,
                tool_result=tc_result,
                observation=observation,
                error=error,
                is_submit=is_submit,
            ))
            step_num += 1
            # Only attach thinking to the first tool call of this message
            thinking = None

    return AgentTrajectory(
        world_id=world_id,
        seed=seed,
        target_node=problem.target_node,
        target_states=problem.target_states,
        budget=result.budget_total,
        budget_used=result.budget_used,
        steps=steps,
        submitted_answer=result.submitted_answer,
        reasoning=result.reasoning,
        confidence=result.confidence,
        score=result.score.functional_score if result.score else None,
    )


def export_agent_trajectories(
    trajectories: list[AgentTrajectory], path: Path
) -> None:
    """Export agent trajectories to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for traj in trajectories:
            f.write(traj.model_dump_json() + "\n")


__all__ = [
    "AgentTrajectory",
    "AgentTrajectoryStep",
    "export_agent_trajectories",
    "extract_agent_trajectory",
]
