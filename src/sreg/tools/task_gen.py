"""TaskGenTool: formulates verifiable tasks from worlds."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import networkx as nx
import numpy as np
from pgmpy.inference import CausalInference

from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.world.pgmpy_utils import world_to_pgmpy

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sreg.models.case_plan import CasePlan


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
        bundle_types = [
            TaskType.INFER_TARGET,
            TaskType.NEXT_BEST_OBSERVATION,
            TaskType.HYPOTHESIS_SELECTION,
        ]
        tasks: dict[TaskType, Task] = {}
        for task_type in bundle_types:
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
        if spec.type == TaskType.CAUSAL_EFFECT:
            return self._causal_effect_task(world, spec, seed)
        if spec.type == TaskType.BEST_INTERVENTION:
            return self._best_intervention_task(world, spec, seed)
        if spec.type == TaskType.ADJUSTMENT_SET:
            return self._adjustment_set_task(world, spec, seed)
        if spec.type == TaskType.COMPARE_INTERVENTIONS:
            return self._compare_interventions_task(world, spec, seed)
        if spec.type == TaskType.SHOULD_CONDITION:
            return self._should_condition_task(world, spec, seed)
        if spec.type == TaskType.INFER_LATENT_CAUSE:
            return self._infer_latent_cause_task(world, spec, seed)
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
            f"You have a research budget of {spec.max_budget} units. "
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

        # Hypothesis D: Dirichlet-sampled distractor.
        # The old "reversed posterior" approach produced near-identical
        # distributions when the posterior was symmetric (e.g. [0.08, 0.83, 0.08]
        # reversed = [0.08, 0.83, 0.08]). A random Dirichlet sample is a
        # genuinely different distribution that's always distinguishable.
        dirichlet_vals = rng.dirichlet([1.0] * len(states))
        hypotheses["D"] = {s: round(v, 4) for s, v in zip(states, dirichlet_vals)}

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

        # Check distinguishability: all distractors must have KL > 0.05
        # If any distractor is too close to the correct answer, log a warning.
        distractor_kls = [kl for kl in kl_scores.values() if kl > 1e-9]
        if distractor_kls and min(distractor_kls) < 0.05:
            logger.warning(
                "hypothesis_selection: min distractor KL=%.4f < 0.05 "
                "(near-indistinguishable hypotheses) for world %s",
                min(distractor_kls), world.id,
            )

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


    def _causal_effect_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        solver = ExactBayesSolver(world)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        rng = np.random.default_rng(seed)

        # Use hint if provided and valid
        hint_node = spec.intervention_node
        if hint_node and hint_node in obs_nodes:
            intervention_node = hint_node
        else:
            # Find observable nodes with a causal effect on target
            causal_nodes = []
            for node in obs_nodes:
                node_obj = next(n for n in world.nodes if n.name == node)
                states = node_obj.states
                dist_first = solver.causal_query(target, do={node: states[0]})
                dist_last = solver.causal_query(target, do={node: states[-1]})
                max_diff = max(
                    abs(dist_first[s] - dist_last[s])
                    for s in dist_first
                )
                if max_diff > 0.02:
                    causal_nodes.append((node, max_diff))

            if not causal_nodes:
                causal_nodes = [(obs_nodes[0], 0.0)]

            # Pick an intervention node (weighted toward stronger effects)
            causal_nodes.sort(key=lambda x: x[1], reverse=True)
            weights = np.array([c[1] for c in causal_nodes])
            if weights.sum() > 0:
                weights = weights / weights.sum()
            else:
                weights = np.ones(len(causal_nodes)) / len(causal_nodes)
            chosen_idx = rng.choice(len(causal_nodes), p=weights)
            intervention_node = causal_nodes[chosen_idx][0]

        # Pick an intervention value
        int_node_obj = next(n for n in world.nodes if n.name == intervention_node)
        int_state = int_node_obj.states[rng.choice(len(int_node_obj.states))]

        # Compute P(target | do(intervention_node = int_state))
        do_dist = solver.causal_query(target, do={intervention_node: int_state})

        # Available evidence: all obs nodes except the intervention node
        remaining = [n for n in obs_nodes if n != intervention_node]

        target_node_obj = next(n for n in world.nodes if n.name == target)
        state_list = ", ".join(target_node_obj.states)

        question = (
            f"If we intervene and set '{intervention_node}' to '{int_state}', "
            f"what would be the probability distribution over '{target}' "
            f"(possible states: {state_list})? "
            f"This is a causal question: you are asked about the effect of an "
            f"intervention (do-operation), not just an observation."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=remaining,
            correct_answer={s: round(p, 6) for s, p in do_dist.items()},
            scoring_method="kl_divergence",
            intervention={intervention_node: int_state},
        )

    def _best_intervention_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        solver = ExactBayesSolver(world)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        target_node_obj = next(n for n in world.nodes if n.name == target)
        rng = np.random.default_rng(seed)

        # Use hint if provided and valid
        if spec.desired_state and spec.desired_state in target_node_obj.states:
            desired_state = spec.desired_state
        else:
            desired_state = target_node_obj.states[rng.choice(len(target_node_obj.states))]

        # Compute effect of each possible single-variable intervention
        intervention_effects: dict[str, float] = {}
        for node_name in obs_nodes:
            node_obj = next(n for n in world.nodes if n.name == node_name)
            for state in node_obj.states:
                do_dist = solver.causal_query(target, do={node_name: state})
                effect = do_dist.get(desired_state, 0.0)
                intervention_effects[f"{node_name}:{state}"] = round(effect, 6)

        # Find optimal intervention
        best_key = max(intervention_effects, key=intervention_effects.get)
        best_node, best_state = best_key.split(":", 1)

        # Also compute the baseline (prior probability without intervention)
        prior = solver.posterior(target)
        baseline = prior.get(desired_state, 0.0)

        question = (
            f"You want to maximize the probability of '{target}' being "
            f"'{desired_state}' (current baseline probability: {baseline:.2f}). "
            f"You can intervene on ONE variable by setting it to a specific value. "
            f"Which variable would you set, and to what value? "
            f"Available variables: {obs_nodes}. "
            f"This is a causal question about interventions (do-operations), "
            f"not observations."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=obs_nodes,
            correct_answer=intervention_effects,
            scoring_method="intervention_effect_ratio",
            intervention={best_node: best_state},
        )

    def _compare_interventions_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        solver = ExactBayesSolver(world)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        target_node_obj = next(n for n in world.nodes if n.name == target)
        rng = np.random.default_rng(seed)

        # Use hint if provided and valid
        if spec.desired_state and spec.desired_state in target_node_obj.states:
            desired_state = spec.desired_state
        else:
            desired_state = target_node_obj.states[rng.choice(len(target_node_obj.states))]

        # Compute effect of each possible intervention (same as best_intervention)
        intervention_effects: dict[str, float] = {}
        for node_name in obs_nodes:
            node_obj = next(n for n in world.nodes if n.name == node_name)
            for state in node_obj.states:
                do_dist = solver.causal_query(target, do={node_name: state})
                effect = do_dist.get(desired_state, 0.0)
                intervention_effects[f"{node_name}:{state}"] = round(effect, 6)

        # Group by node: best intervention per node
        by_node: dict[str, list[tuple[str, float]]] = {}
        for key, eff in intervention_effects.items():
            node_name = key.split(":")[0]
            by_node.setdefault(node_name, []).append((key, eff))

        node_bests: list[tuple[str, float]] = []
        for node_name, entries in by_node.items():
            best_entry = max(entries, key=lambda e: e[1])
            node_bests.append(best_entry)

        # Use compare_nodes hint if provided and valid (2 distinct existing nodes)
        hint_nodes = spec.compare_nodes
        used_hint = False
        if hint_nodes and len(hint_nodes) == 2 and len(set(hint_nodes)) == 2:
            valid = all(n in by_node for n in hint_nodes)
            if valid:
                pick_a = max(by_node[hint_nodes[0]], key=lambda e: e[1])
                pick_b = max(by_node[hint_nodes[1]], key=lambda e: e[1])
                used_hint = True

        if not used_hint:
            # Sort by effect and pick two with the largest gap
            node_bests.sort(key=lambda e: e[1], reverse=True)

            if len(node_bests) < 2:
                all_sorted = sorted(
                    intervention_effects.items(), key=lambda e: e[1], reverse=True
                )
                pick_a = all_sorted[0]
                pick_b = all_sorted[-1]
            else:
                pick_a = node_bests[0]
                pick_b = node_bests[-1]
                if abs(pick_a[1] - pick_b[1]) < 1e-9 and len(node_bests) > 2:
                    for candidate in reversed(node_bests[1:]):
                        if abs(pick_a[1] - candidate[1]) > 1e-9:
                            pick_b = candidate
                            break

        key_a, effect_a = pick_a
        key_b, effect_b = pick_b
        node_a, state_a = key_a.split(":", 1)
        node_b, state_b = key_b.split(":", 1)

        # Randomize presentation order so "A" isn't always the better one
        if rng.random() < 0.5:
            key_a, effect_a, node_a, state_a, key_b, effect_b, node_b, state_b = (
                key_b, effect_b, node_b, state_b, key_a, effect_a, node_a, state_a,
            )

        # Correct answer: which intervention has higher P(target=desired | do(...))
        correct_answer = {
            key_a: round(effect_a, 6),
            key_b: round(effect_b, 6),
        }

        # The better intervention goes in the intervention field
        if effect_a >= effect_b:
            better_node, better_state = node_a, state_a
        else:
            better_node, better_state = node_b, state_b

        question = (
            f"Your team is debating between two possible interventions to "
            f"maximize '{target}' being '{desired_state}'. "
            f"Intervention A: set '{node_a}' to '{state_a}'. "
            f"Intervention B: set '{node_b}' to '{state_b}'. "
            f"Which intervention would have a larger causal effect on "
            f"the probability of '{target}' being '{desired_state}'? "
            f"This is about do-operations (interventions), not observations. "
            f"Answer 'A' or 'B'."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=obs_nodes,
            correct_answer=correct_answer,
            scoring_method="compare_interventions",
            intervention={better_node: better_state},
        )

    def _infer_latent_cause_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        solver = ExactBayesSolver(world)
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        latent_nodes = [n for n in world.nodes if n.type == NodeType.LATENT]
        rng = np.random.default_rng(seed)

        if not latent_nodes:
            raise ValueError(
                "Cannot generate infer_latent_cause task: world has no latent nodes"
            )

        # Pick a latent node
        latent_node = latent_nodes[rng.choice(len(latent_nodes))]

        # Sample a true state and give some evidence
        true_state = solver.sample_state(seed=seed)

        # Give 1 to N-2 observations (leave room for uncertainty)
        max_given = max(1, len(obs_nodes) - 2)
        num_given = int(rng.integers(1, max_given + 1))
        shuffled = list(obs_nodes)
        rng.shuffle(shuffled)
        given_nodes = shuffled[:num_given]
        given_evidence = {n: true_state[n] for n in given_nodes}

        # Compute posterior of the latent given evidence
        posterior = solver.posterior(latent_node.name, evidence=given_evidence)

        state_list = ", ".join(latent_node.states)
        evidence_desc = ", ".join(f"'{k}' = '{v}'" for k, v in given_evidence.items())
        question = (
            f"Based on the observed data ({evidence_desc}), estimate the "
            f"probability distribution over the possible states of the hidden "
            f"variable '{latent_node.name}' (possible states: {state_list}). "
            f"This variable cannot be directly observed — you must infer it "
            f"from the available evidence."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=latent_node.name,
            available_evidence=obs_nodes,
            correct_answer=posterior,
            scoring_method="kl_divergence",
            given_evidence=given_evidence,
        )

    def _should_condition_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        model = world_to_pgmpy(world)
        ci = CausalInference(model)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        rng = np.random.default_rng(seed)

        # Classify (treatment, suggested_var) pairs as "should" or "should not" condition
        candidates_yes: list[tuple[str, str]] = []  # (treatment, suggested_var)
        candidates_no: list[tuple[str, str]] = []

        for x in obs_nodes:
            if x == target:
                continue
            try:
                adj_sets = ci.get_all_backdoor_adjustment_sets(x, target)
            except ValueError:
                continue

            all_in_sets: set[str] = set()
            for s in adj_sets:
                all_in_sets.update(s)

            desc_of_x = nx.descendants(model, x)

            for z in obs_nodes:
                if z == x or z == target:
                    continue
                if z in all_in_sets:
                    candidates_yes.append((x, z))
                elif z in desc_of_x:
                    candidates_no.append((x, z))

        # Check if plan provided specific hints
        hint_treatment = spec.intervention_node
        hint_condition = spec.condition_variable
        used_hint = False

        if hint_treatment and hint_condition:
            pair = (hint_treatment, hint_condition)
            if pair in candidates_yes:
                treatment, suggested = pair
                correct_answer = {"yes": 1.0}
                used_hint = True
            elif pair in candidates_no:
                treatment, suggested = pair
                correct_answer = {"no": 1.0}
                used_hint = True

        if not used_hint:
            # Randomize which type of question to ask
            rng.shuffle(candidates_yes)
            rng.shuffle(candidates_no)

            if candidates_no and candidates_yes:
                ask_no = bool(rng.random() < 0.5)
            elif candidates_no:
                ask_no = True
            elif candidates_yes:
                ask_no = False
            else:
                # No clear candidates — fallback: pick any pair, treat as "no"
                treatment = obs_nodes[0] if obs_nodes[0] != target else obs_nodes[1]
                others = [z for z in obs_nodes if z != treatment and z != target]
                suggested = others[0] if others else treatment
                ask_no = True
                candidates_no = [(treatment, suggested)]

            if ask_no:
                treatment, suggested = candidates_no[0]
                correct_answer = {"no": 1.0}
            else:
                treatment, suggested = candidates_yes[0]
                correct_answer = {"yes": 1.0}

        question = (
            f"You are analyzing the causal effect of '{treatment}' on '{target}' "
            f"using observational data. A colleague suggests controlling for "
            f"'{suggested}' in your analysis. "
            f"Is this a good idea? Should you include '{suggested}' as a "
            f"control variable? Answer 'yes' or 'no', and explain your reasoning."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=obs_nodes,
            correct_answer=correct_answer,
            scoring_method="should_condition",
            intervention={treatment: suggested},
        )

    def _adjustment_set_task(
        self, world: World, spec: TaskSpec, seed: int
    ) -> Task:
        model = world_to_pgmpy(world)
        ci = CausalInference(model)
        target = spec.target_node
        obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
        obs_set = set(obs_nodes)
        rng = np.random.default_rng(seed)

        # Find treatment nodes and classify by identifiability
        # Priority 3: confounded + identifiable with observables (best — real science)
        # Priority 1: no confounding, empty set valid (trivial but correct)
        # Priority 0: confounded but NOT identifiable with observables (also valuable!)
        candidates = []
        for x in obs_nodes:
            if x == target:
                continue
            try:
                adj_sets = ci.get_all_backdoor_adjustment_sets(x, target)
            except ValueError:
                # pgmpy raises ValueError when no valid adjustment set exists at all
                # (e.g., X is a descendant of Y with no causal path X -> Y)
                candidates.append((x, [["_not_identifiable_"]], 0))
                continue
            obs_only_sets = [
                sorted(s) for s in adj_sets if all(v in obs_set for v in s)
            ]
            # No backdoor paths at all → empty set is trivially valid
            empty_valid = len(adj_sets) == 0 or frozenset() in adj_sets
            has_confounding = not empty_valid

            if has_confounding and obs_only_sets:
                # Confounded AND identifiable with observables
                candidates.append((x, obs_only_sets, 3))
            elif has_confounding and not obs_only_sets:
                # Confounded but NOT identifiable — hidden confounder required
                candidates.append((x, [["_not_identifiable_"]], 0))
            elif not has_confounding:
                # No confounding — empty set is correct
                candidates.append((x, [[]], 1))

        if not candidates:
            x = obs_nodes[0] if obs_nodes[0] != target else obs_nodes[1]
            candidates = [(x, [[]], 1)]

        # Use hint if provided and valid
        hint_node = spec.intervention_node
        chosen = None
        if hint_node:
            for c in candidates:
                if c[0] == hint_node:
                    chosen = c
                    break

        if chosen is None:
            # Prefer identifiable confounded pairs (priority 3), then unconfounded (1),
            # then not-identifiable (0)
            candidates.sort(key=lambda c: c[2], reverse=True)
            best_priority = candidates[0][2]
            top_candidates = [c for c in candidates if c[2] == best_priority]
            chosen = top_candidates[rng.choice(len(top_candidates))]

        treatment_node = chosen[0]
        valid_sets = chosen[1]
        chosen_priority = chosen[2]

        # Build correct_answer: each valid minimal set as comma-joined key -> 1.0
        correct_answer: dict[str, float] = {}
        for s in valid_sets:
            if s == ["_not_identifiable_"]:
                correct_answer["_not_identifiable_"] = 1.0
            elif s:
                correct_answer[",".join(s)] = 1.0
            else:
                correct_answer["_empty_"] = 1.0

        # Available variables for the adjustment set (exclude treatment and target)
        available = [n for n in obs_nodes if n != treatment_node and n != target]

        is_identifiable_confounded = chosen_priority == 3
        is_not_identifiable = "_not_identifiable_" in correct_answer
        if is_identifiable_confounded:
            question = (
                f"You want to estimate the causal effect of '{treatment_node}' on "
                f"'{target}' using observational data. There may be confounding "
                f"variables that create spurious associations. Which variables "
                f"should you control for (include as covariates) in your analysis? "
                f"Available variables: {available}. "
                f"Provide the minimal set of variables needed to block all "
                f"backdoor paths."
            )
        elif is_not_identifiable:
            question = (
                f"You want to estimate the causal effect of '{treatment_node}' on "
                f"'{target}' using observational data. "
                f"Available variables: {available}. "
                f"Determine whether this causal effect can be identified from "
                f"observational data by controlling for available variables. "
                f"If the required confounders are not measurable, the effect is "
                f"not identifiable via the backdoor criterion."
            )
        else:
            question = (
                f"You want to estimate the causal effect of '{treatment_node}' on "
                f"'{target}' using observational data. "
                f"Which variables should you control for (include as covariates) "
                f"in your analysis? "
                f"Available variables: {available}. "
                f"If no confounding exists, controlling for no variables is correct."
            )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=available,
            correct_answer=correct_answer,
            scoring_method="adjustment_set_match",
            intervention={treatment_node: "treatment"},
        )

    # Eval types where the auto-generated question text is safe to override
    # because the correct_answer does not reference specific node names or
    # interventions that the custom question_text might not mention.
    _SAFE_QUESTION_OVERRIDE_TYPES = frozenset({
        TaskType.INFER_TARGET,
        TaskType.NEXT_BEST_OBSERVATION,
        TaskType.HYPOTHESIS_SELECTION,
        TaskType.INFER_LATENT_CAUSE,
    })

    # Types where the auto-generated question contains specific intervention
    # states that MUST match the correct_answer. Overriding these with the
    # orchestrator's question_text risks semantic inversion (e.g., question
    # says "increasing resistance" but answer key is "resistance:weak").
    _NEVER_OVERRIDE_QUESTION_TYPES = frozenset({
        TaskType.COMPARE_INTERVENTIONS,
    })

    def generate_from_plan(
        self,
        world: World,
        plan: "CasePlan",
        seed: int = 0,
    ) -> list[Task]:
        """Generate tasks driven by a CasePlan instead of fixed task types.

        Node hints in the plan (intervention_node, desired_state, etc.) are
        passed through to the task generator so that the generated answer
        references the same nodes as the plan's question_text.

        Question text override rules:
        - "Safe" types (infer_target, NBO, hypothesis_selection, infer_latent_cause):
          always override with plan's question_text.
        - Other types: override ONLY when ``_hints_honored()`` confirms the
          generated task actually used the hinted nodes.  If hints were invalid
          or ignored, the auto-generated question is kept to prevent mismatch.
        """
        tasks: list[Task] = []
        for i, q in enumerate(plan.questions):
            spec = TaskSpec(
                type=q.eval_type,
                target_node=q.target_node,
                max_budget=plan.shared_budget,
                intervention_node=q.intervention_node,
                desired_state=q.desired_state,
                compare_nodes=q.compare_nodes,
                condition_variable=q.condition_variable,
            )
            task = self.generate(world, spec, seed=seed + i)

            # Decide whether to override the auto-generated question text.
            # Safe types (answer doesn't reference specific nodes): always OK.
            # Unsafe types: only override when the generated task ACTUALLY USED
            # the hinted nodes (not just when hints were provided).
            if q.eval_type in self._NEVER_OVERRIDE_QUESTION_TYPES:
                # Keep auto-generated question — it contains the exact states
                # from correct_answer. Overriding risks semantic inversion.
                pass
            elif q.eval_type in self._SAFE_QUESTION_OVERRIDE_TYPES:
                task = task.model_copy(update={"question": q.question_text})
            elif self._hints_honored(q, task):
                task = task.model_copy(update={"question": q.question_text})

            # Consistency check: verify question mentions key nodes from answer
            self._check_question_answer_consistency(task, q.eval_type)

            tasks.append(task)
        return tasks

    @staticmethod
    def _check_question_answer_consistency(
        task: Task, eval_type: TaskType
    ) -> None:
        """Log a warning if the question text doesn't mention nodes from the answer.

        This catches mismatches where the question asks about one thing but the
        answer is computed for something else. Only checks node-sensitive types.
        """
        if not task.correct_answer or not task.question:
            return

        question_lower = task.question.lower()

        # Extract relevant node names depending on eval type
        nodes_to_check: list[str] = []
        if eval_type in (TaskType.CAUSAL_EFFECT, TaskType.ADJUSTMENT_SET,
                         TaskType.SHOULD_CONDITION):
            # intervention dict has the key node names
            if task.intervention:
                nodes_to_check = list(task.intervention.keys())
        elif eval_type == TaskType.COMPARE_INTERVENTIONS:
            # answer keys are "node:state", extract node part
            nodes_to_check = [k.split(":")[0] for k in task.correct_answer]
        elif eval_type == TaskType.BEST_INTERVENTION:
            # No specific node to check in question (any node can be the answer)
            return
        else:
            # Safe types — no check needed
            return

        missing = [n for n in nodes_to_check if n.lower() not in question_lower]
        if missing:
            logger.warning(
                "Question/answer consistency: task %s (%s) — question does not "
                "mention nodes from the answer: %s. Question: '%.80s...'",
                task.id, eval_type.value, missing, task.question,
            )

    @staticmethod
    def _hints_honored(q: "EvalQuestionPlan", task: Task) -> bool:
        """Check whether the generated task actually used the plan's hints.

        Only returns True when the task's concrete nodes/states match what
        the plan specified.  If hints were provided but ignored (invalid
        node, not in candidates, etc.), returns False so the auto-generated
        question is kept — preventing question/answer mismatch.
        """
        et = q.eval_type
        inv = task.intervention  # {node: state} or {treatment: suggested}

        if et == TaskType.CAUSAL_EFFECT:
            return bool(q.intervention_node and q.intervention_node in inv)

        if et == TaskType.BEST_INTERVENTION:
            # The generator uses desired_state if it's a valid state for the target.
            # Verify by checking the auto-generated question mentions it.
            return bool(q.desired_state and q.desired_state in task.question)

        if et == TaskType.COMPARE_INTERVENTIONS:
            if not q.compare_nodes or len(q.compare_nodes) != 2:
                return False
            if len(set(q.compare_nodes)) != 2:
                return False
            answer_nodes = {k.split(":")[0] for k in task.correct_answer}
            nodes_match = set(q.compare_nodes) == answer_nodes
            # If desired_state was also hinted, verify it was used
            if q.desired_state and q.desired_state not in task.question:
                return False
            return nodes_match

        if et == TaskType.ADJUSTMENT_SET:
            return bool(q.intervention_node and q.intervention_node in inv)

        if et == TaskType.SHOULD_CONDITION:
            if not (q.intervention_node and q.condition_variable):
                return False
            return inv == {q.intervention_node: q.condition_variable}

        return False


__all__ = ["TaskGenTool"]
