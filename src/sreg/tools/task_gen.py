"""TaskGenTool: formulates verifiable tasks from worlds."""

from __future__ import annotations

import numpy as np

from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver


class TaskGenTool:
    """Generates tasks from a world and task specification."""

    def generate_all(
        self,
        world: World,
        target_node: str = "target_outcome",
        max_budget: int = 5,
        seed: int = 0,
    ) -> TaskBundle:
        """Generate all 3 task types from the same world.

        Returns a TaskBundle grouping infer_target, next_best_observation,
        and hypothesis_selection tasks derived from the same world and seed.
        """
        tasks: dict[TaskType, Task] = {}
        for task_type in TaskType:
            spec = TaskSpec(type=task_type, target_node=target_node, max_budget=max_budget)
            tasks[task_type] = self.generate(world, spec, seed=seed)
        return TaskBundle(
            world_id=world.id,
            target_node=target_node,
            seed=seed,
            tasks=tasks,
        )

    def generate(self, world: World, spec: TaskSpec, seed: int = 0) -> Task:
        """Generate a task from a world and specification.

        For infer_target: the correct answer is the prior distribution P(target).
        For next_best_observation: the correct answer is an IG ranking of available nodes.
        For hypothesis_selection: the correct answer maps hypothesis labels to KL from true.
        """
        if spec.type == TaskType.INFER_TARGET:
            return self._infer_target_task(world, spec)
        if spec.type == TaskType.NEXT_BEST_OBSERVATION:
            return self._next_best_observation_task(world, spec, seed)
        if spec.type == TaskType.HYPOTHESIS_SELECTION:
            return self._hypothesis_selection_task(world, spec, seed)
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


    def _hypothesis_selection_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        solver = ExactBayesSolver(world)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        target_node = next(n for n in world.nodes if n.name == target)
        states = target_node.states

        # Sample a true state and give some evidence
        true_state = solver.sample_state(seed=seed)
        rng = np.random.default_rng(seed)

        # Give 1 to N-1 observations
        max_given = max(1, len(obs_nodes) - 1)
        num_given = rng.integers(1, max_given + 1)
        shuffled = list(obs_nodes)
        rng.shuffle(shuffled)
        given_nodes = shuffled[:num_given]
        remaining_nodes = [n for n in obs_nodes if n not in given_nodes]

        given_evidence = {n: true_state[n] for n in given_nodes}

        # True posterior given evidence
        true_posterior = solver.posterior(target, given_evidence)

        # Generate hypotheses: true posterior + distractors
        hypotheses: dict[str, dict[str, float]] = {}

        # Hypothesis A: the true posterior (correct answer)
        hypotheses["A"] = {s: round(p, 4) for s, p in true_posterior.items()}

        # Hypothesis B: the prior (no evidence)
        prior = solver.posterior(target)
        hypotheses["B"] = {s: round(p, 4) for s, p in prior.items()}

        # Hypothesis C: uniform distribution
        uniform_p = 1.0 / len(states)
        hypotheses["C"] = {s: round(uniform_p, 4) for s in states}

        # Hypothesis D: reversed posterior (high becomes low)
        reversed_vals = list(reversed(list(true_posterior.values())))
        hypotheses["D"] = {s: round(v, 4) for s, v in zip(states, reversed_vals)}

        # Shuffle hypothesis labels so the correct one isn't always A
        labels = list(hypotheses.keys())
        dists = [hypotheses[l] for l in labels]
        perm = rng.permutation(len(labels))
        shuffled_labels = [chr(ord("A") + i) for i in range(len(labels))]
        shuffled_hypotheses: dict[str, dict[str, float]] = {}
        correct_label = None
        for new_idx, old_idx in enumerate(perm):
            new_label = shuffled_labels[new_idx]
            shuffled_hypotheses[new_label] = dists[old_idx]
            if labels[old_idx] == "A":  # the true posterior
                correct_label = new_label

        # Compute KL of each hypothesis from true posterior (for scoring)
        from sreg.tools.verifier import VerifierTool

        verifier = VerifierTool()
        kl_scores: dict[str, float] = {}
        for label, dist in shuffled_hypotheses.items():
            kl = verifier.kl_divergence(dist, true_posterior)
            kl_scores[label] = round(kl, 6)

        # Build question text
        evidence_desc = ", ".join(f"{k}={v}" for k, v in given_evidence.items())
        hyp_lines = []
        for label, dist in shuffled_hypotheses.items():
            dist_str = ", ".join(f"{s}={p:.2f}" for s, p in dist.items())
            hyp_lines.append(f"  {label}: {dist_str}")
        hyp_text = "\n".join(hyp_lines)

        question = (
            f"You are investigating '{target}'. "
            f"You have observed: {evidence_desc}.\n\n"
            f"Which of these hypotheses best describes the distribution of '{target}'?\n"
            f"{hyp_text}\n\n"
            f"Choose the most plausible hypothesis (A, B, C, or D)."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=remaining_nodes,
            correct_answer=kl_scores,
            scoring_method="hypothesis_accuracy",
            given_evidence=given_evidence,
            hypotheses=shuffled_hypotheses,
        )


__all__ = ["TaskGenTool"]
