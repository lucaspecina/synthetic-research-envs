"""TaskGenTool: formulates verifiable tasks from worlds."""

from __future__ import annotations

from sreg.models.task import Task, TaskSpec, TaskType
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver


class TaskGenTool:
    """Generates tasks from a world and task specification."""

    def generate(self, world: World, spec: TaskSpec) -> Task:
        """Generate a task from a world and specification.

        For infer_target: the correct answer is the prior distribution P(target).
        The agent must observe evidence and submit a posterior estimate.
        """
        if spec.type == TaskType.INFER_TARGET:
            return self._infer_target_task(world, spec)
        raise ValueError(f"Unsupported task type: {spec.type}")

    def _infer_target_task(self, world: World, spec: TaskSpec) -> Task:
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        target = spec.target_node

        # Correct answer is the prior (no evidence) — agent must beat this by observing
        solver = ExactBayesSolver(world)
        prior = solver.posterior(target)

        target_node = next(n for n in world.nodes if n.name == target)
        state_list = ", ".join(target_node.states)

        question = (
            f"Estimate the probability distribution over the states of '{target}' "
            f"(possible states: {state_list}). "
            f"You have a budget of {spec.max_budget} observations. "
            f"Choose which variables to observe to refine your estimate, "
            f"then submit your final distribution."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=obs_nodes,
            correct_answer=prior,
            scoring_method="kl_divergence",
        )


__all__ = ["TaskGenTool"]
