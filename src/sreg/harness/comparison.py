"""Side-by-side comparison of agent vs teacher trajectories."""

from __future__ import annotations

from pydantic import BaseModel

from sreg.harness.agent_trajectory import AgentTrajectory
from sreg.harness.trajectory import TeacherTrajectory


class TrajectoryComparison(BaseModel):
    """Side-by-side comparison of agent vs teacher on the same problem."""

    world_id: str
    seed: int
    target_node: str
    true_state: str
    budget: int

    teacher_steps: list[dict]
    agent_steps: list[dict]

    teacher_final_posterior: dict[str, float]
    agent_final_posterior: dict[str, float] | None

    teacher_kl: float
    agent_kl: float | None

    agent_budget_used: int
    teacher_budget_used: int

    verdict: str


def compare_trajectories(
    teacher: TeacherTrajectory,
    agent: AgentTrajectory,
) -> TrajectoryComparison:
    """Build a side-by-side comparison from teacher and agent trajectories.

    Args:
        teacher: TeacherTrajectory from generate_teacher_trajectory().
        agent: AgentTrajectory from extract_agent_trajectory().

    Returns:
        A TrajectoryComparison with aligned steps and verdict.
    """
    teacher_steps = [
        {
            "step": s.step,
            "action": s.action_node,
            "observation": f"{s.action_node} = {s.observed_state}",
            "info_gain": round(s.info_gain, 6),
            "posterior": {k: round(v, 4) for k, v in s.posterior.items()},
        }
        for s in teacher.steps
    ]

    agent_steps = []
    for s in agent.steps:
        entry: dict = {"step": s.step}
        if s.thinking:
            # Truncate for readability
            entry["thinking"] = s.thinking[:200] + ("..." if len(s.thinking) > 200 else "")
        if s.tool_call:
            entry["action"] = s.tool_call
            if s.tool_args:
                entry["args"] = s.tool_args
        if s.observation:
            entry["observation"] = s.observation
        if s.error:
            entry["error"] = s.error
        if s.is_submit and agent.submitted_answer:
            entry["submitted"] = {k: round(v, 4) for k, v in agent.submitted_answer.items()}
        agent_steps.append(entry)

    # Verdict
    if agent.submitted_answer is None:
        verdict = "NO_SUBMIT"
    elif agent.score is None:
        verdict = "NO_SCORE"
    elif agent.score < 0.1:
        verdict = "EXCELLENT"
    elif agent.score < 0.5:
        verdict = "GOOD"
    elif agent.score < 1.5:
        verdict = "FAIR"
    else:
        verdict = "POOR"

    return TrajectoryComparison(
        world_id=teacher.world_id,
        seed=teacher.seed,
        target_node=teacher.target_node,
        true_state=teacher.true_state,
        budget=teacher.budget,
        teacher_steps=teacher_steps,
        agent_steps=agent_steps,
        teacher_final_posterior={
            k: round(v, 6) for k, v in teacher.final_posterior.items()
        },
        agent_final_posterior=(
            {k: round(v, 6) for k, v in agent.submitted_answer.items()}
            if agent.submitted_answer
            else None
        ),
        teacher_kl=0.0,  # Teacher is optimal, KL with itself is 0
        agent_kl=agent.score,
        agent_budget_used=agent.budget_used,
        teacher_budget_used=len(teacher.steps),
        verdict=verdict,
    )


__all__ = [
    "TrajectoryComparison",
    "compare_trajectories",
]
