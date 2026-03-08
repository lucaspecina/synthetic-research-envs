"""Teacher trajectory generation and JSONL export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionType
from sreg.models.research_problem import ResearchProblem
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool


@dataclass
class TrajectoryStep:
    """A single step in the teacher's trajectory."""

    step: int
    action_node: str
    observed_state: str
    info_gain: float
    posterior: dict[str, float]


@dataclass
class TeacherTrajectory:
    """Complete teacher trajectory for a problem."""

    world_id: str
    seed: int
    target_node: str
    target_states: list[str]
    true_state: str
    budget: int
    steps: list[TrajectoryStep] = field(default_factory=list)
    final_posterior: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for JSON export."""
        return {
            "world_id": self.world_id,
            "seed": self.seed,
            "target_node": self.target_node,
            "target_states": self.target_states,
            "true_state": self.true_state,
            "budget": self.budget,
            "steps": [
                {
                    "step": s.step,
                    "action_node": s.action_node,
                    "observed_state": s.observed_state,
                    "info_gain": round(s.info_gain, 6),
                    "posterior": {k: round(v, 6) for k, v in s.posterior.items()},
                }
                for s in self.steps
            ],
            "final_posterior": {k: round(v, 6) for k, v in self.final_posterior.items()},
        }


def generate_teacher_trajectory(
    world: World,
    problem: ResearchProblem,
    seed: int = 0,
) -> TeacherTrajectory:
    """Run the teacher solver and record its full trajectory.

    Args:
        world: The World (formal layer).
        problem: The ResearchProblem (defines budget, target, available actions).
        seed: Seed for sampling the true state.

    Returns:
        A TeacherTrajectory with every step recorded.
    """
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    ep_tool = EpisodeGenTool()
    episode = ep_tool.generate(world, EpisodeGenConfig(budget=problem.budget, seed=seed))
    runner = EpisodeRunner(world, episode, true_state)

    obs_nodes = list(episode.available_nodes)
    evidence: dict[str, str] = {}

    traj = TeacherTrajectory(
        world_id=world.id,
        seed=seed,
        target_node=problem.target_node,
        target_states=problem.target_states,
        true_state=true_state[problem.target_node],
        budget=problem.budget,
    )

    for step_num in range(min(episode.budget, len(obs_nodes))):
        available = [n for n in obs_nodes if n not in evidence]
        if not available:
            break
        output = solver.optimal_action(problem.target_node, evidence, available)
        if output.recommended_action is None:
            break

        # Calculate info gain before observing
        ig = solver.information_gain(problem.target_node, evidence, output.recommended_action.node)

        result = runner.step(output.recommended_action)
        node = result.observation.node
        state = result.observation.state
        evidence[node] = state

        # Posterior after this observation
        posterior = solver.posterior(problem.target_node, evidence)

        traj.steps.append(
            TrajectoryStep(
                step=step_num,
                action_node=node,
                observed_state=state,
                info_gain=ig,
                posterior=posterior,
            )
        )

    traj.final_posterior = runner.true_posterior(problem.target_node)

    # Submit so runner is finished
    runner.step(Action(type=ActionType.SUBMIT, answer=traj.final_posterior, confidence=1.0))

    return traj


def export_trajectories(trajectories: list[TeacherTrajectory], path: Path) -> None:
    """Export a list of trajectories to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for traj in trajectories:
            f.write(json.dumps(traj.to_dict()) + "\n")


__all__ = [
    "TeacherTrajectory",
    "TrajectoryStep",
    "export_trajectories",
    "generate_teacher_trajectory",
]
