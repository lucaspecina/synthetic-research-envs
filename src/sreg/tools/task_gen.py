"""TaskGenTool: formulates verifiable tasks from worlds."""

from __future__ import annotations

import numpy as np

from sreg.models.task import Task, TaskSpec, TaskType
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver


class TaskGenTool:
    """Generates tasks from a world and task specification."""

    def generate(self, world: World, spec: TaskSpec, seed: int = 0) -> Task:
        """Generate a task from a world and specification.

        For infer_target: the correct answer is the prior distribution P(target).
        For next_best_observation: the correct answer is an IG ranking of available nodes.
        """
        if spec.type == TaskType.INFER_TARGET:
            return self._infer_target_task(world, spec)
        if spec.type == TaskType.NEXT_BEST_OBSERVATION:
            return self._next_best_observation_task(world, spec, seed)
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

    def _next_best_observation_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        solver = ExactBayesSolver(world)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]

        # Sample a true state and give the agent some evidence
        true_state = solver.sample_state(seed=seed)
        rng = np.random.default_rng(seed)

        # Give 1 to N-2 observations (leave at least 2 choices)
        max_given = max(1, len(obs_nodes) - 2)
        num_given = rng.integers(1, max_given + 1)
        shuffled = list(obs_nodes)
        rng.shuffle(shuffled)
        given_nodes = shuffled[:num_given]
        remaining_nodes = [n for n in obs_nodes if n not in given_nodes]

        given_evidence = {n: true_state[n] for n in given_nodes}

        # Compute IG ranking for remaining nodes
        ig_ranking: dict[str, float] = {}
        for node in remaining_nodes:
            ig = solver.information_gain(target, given_evidence, node)
            ig_ranking[node] = round(ig, 6)

        best_node = max(ig_ranking, key=ig_ranking.get)

        evidence_desc = ", ".join(f"{k}={v}" for k, v in given_evidence.items())
        question = (
            f"You are investigating '{target}'. "
            f"You have already observed: {evidence_desc}. "
            f"You can measure one more variable from: {remaining_nodes}. "
            f"Which variable would be most informative to observe next?"
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=remaining_nodes,
            correct_answer=ig_ranking,
            scoring_method="info_gain_ratio",
            given_evidence=given_evidence,
        )


__all__ = ["TaskGenTool"]
