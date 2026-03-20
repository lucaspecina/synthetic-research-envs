"""SCMTaskGenTool: generates verifiable tasks from SCMWorld + SCMSolver.

Mirrors TaskGenTool but works with continuous variables instead of discrete BN.

Key differences from TaskGenTool:
- Distributions are represented as bin histograms (dict with bin-range keys).
- Intervention values are floats (percentiles of marginal), not discrete states.
- Graph-based tasks (should_condition, adjustment_set) use SCMWorld.dag directly.
- No dependency on pgmpy.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np

from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)

# Number of bins for discretizing continuous distributions into histograms
_N_BINS = 5


class SCMTaskGenTool:
    """Generates tasks from an SCMWorld and task specification."""

    def generate_all(
        self,
        world: SCMWorld,
        target_node: str,
        max_budget: int = 5,
        seed: int = 0,
    ) -> TaskBundle:
        """Generate the 3 core task types from the same world."""
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

    def generate(self, world: SCMWorld, spec: TaskSpec, seed: int = 0) -> Task:
        """Generate a task from an SCMWorld and specification."""
        if spec.type == TaskType.INFER_TARGET:
            return self._infer_target_task(world, spec, seed)
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

    # ------------------------------------------------------------------
    # Discretization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_bin_edges(
        world: SCMWorld, target: str, n_bins: int = _N_BINS, seed: int = 0
    ) -> np.ndarray:
        """Compute equal-width bin edges covering mean +/- 4*std.

        Uses fixed-width bins so the prior distribution has a real shape
        (e.g., Gaussian peak in center bins). Quantile bins would make the
        prior ~uniform, trivializing infer_target tasks.

        The +/- 4*std range covers >99.99% of Gaussian mass and handles
        shifted interventional distributions without tail loss.
        """
        samples = world.observational_distribution(target, n=10_000, seed=seed)
        mu = float(np.mean(samples))
        sigma = float(np.std(samples))
        if sigma < 1e-10:
            return np.array([mu - 1, mu + 1])
        lo = mu - 4 * sigma
        hi = mu + 4 * sigma
        return np.linspace(lo, hi, n_bins + 1)

    @staticmethod
    def _discretize(samples: np.ndarray, bin_edges: np.ndarray) -> dict[str, float]:
        """Convert continuous samples into a histogram dict.

        Keys are formatted bin ranges like "[1.20, 3.40)".
        Values are probabilities (sum to 1.0).
        """
        hist, _ = np.histogram(samples, bins=bin_edges, density=False)
        total = hist.sum()
        probs = hist / total if total > 0 else hist.astype(float)
        result: dict[str, float] = {}
        for i in range(len(hist)):
            label = f"[{bin_edges[i]:.2f}, {bin_edges[i + 1]:.2f})"
            result[label] = round(float(probs[i]), 6)
        return result

    @staticmethod
    def _obs_nodes(world: SCMWorld) -> list[str]:
        """Observable variables (all except latent)."""
        return world.observable_variables

    # ------------------------------------------------------------------
    # Task generators
    # ------------------------------------------------------------------

    def _infer_target_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)

        bin_edges = self._compute_bin_edges(world, target, seed=seed)
        samples = solver.posterior_samples(target, n=50_000, seed=seed)
        correct_answer = self._discretize(samples, bin_edges)

        bins_desc = ", ".join(correct_answer.keys())
        question = (
            f"Based on the available data, estimate the distribution of '{target}' "
            f"across these ranges: {bins_desc}. "
            f"Analyze the data to refine your estimate, "
            f"then submit probabilities for each range (summing to 1.0)."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=obs_nodes,
            correct_answer=correct_answer,
            scoring_method="kl_divergence",
        )

    def _next_best_observation_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        # Sample a true state and give the agent some evidence
        true_state = solver.sample_state(seed=seed)

        # Give 1 to N-2 observations (leave at least 2 choices)
        max_given = max(1, len(obs_nodes) - 2)
        num_given = int(rng.integers(1, max_given + 1))
        shuffled = list(obs_nodes)
        rng.shuffle(shuffled)
        given_nodes = shuffled[:num_given]
        remaining_nodes = [n for n in obs_nodes if n not in given_nodes]

        # Evidence: continuous values stored as strings
        given_evidence = {n: f"{true_state[n]:.4f}" for n in given_nodes}
        evidence_floats = {n: true_state[n] for n in given_nodes}

        # Compute IG ranking for remaining nodes
        ig_ranking: dict[str, float] = {}
        for node in remaining_nodes:
            ig = solver.information_gain(target, evidence_floats, node, seed=seed)
            ig_ranking[node] = round(ig, 6)

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
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        # Shared bin edges for all hypotheses (consistency is critical)
        bin_edges = self._compute_bin_edges(world, target, seed=seed)
        n_bins = len(bin_edges) - 1

        # Sample a true state and give some evidence
        true_state = solver.sample_state(seed=seed)

        max_given = max(1, len(obs_nodes) - 1)
        num_given = int(rng.integers(1, max_given + 1))
        shuffled = list(obs_nodes)
        rng.shuffle(shuffled)
        given_nodes = shuffled[:num_given]
        remaining_nodes = [n for n in obs_nodes if n not in given_nodes]

        given_evidence = {n: f"{true_state[n]:.4f}" for n in given_nodes}
        evidence_floats = {n: true_state[n] for n in given_nodes}

        # True posterior given evidence
        true_post_samples = solver.posterior_samples(
            target, evidence=evidence_floats, n=50_000, seed=seed
        )
        true_posterior = self._discretize(true_post_samples, bin_edges)

        # Generate hypotheses
        hypotheses: dict[str, dict[str, float]] = {}

        # A: true posterior (correct answer)
        hypotheses["A"] = {k: round(v, 4) for k, v in true_posterior.items()}

        # B: prior (no evidence)
        prior_samples = solver.posterior_samples(target, n=50_000, seed=seed)
        prior = self._discretize(prior_samples, bin_edges)
        hypotheses["B"] = {k: round(v, 4) for k, v in prior.items()}

        # C: uniform distribution
        uniform_p = 1.0 / n_bins
        hypotheses["C"] = {k: round(uniform_p, 4) for k in true_posterior.keys()}

        # D: Dirichlet-sampled distractor
        dirichlet_vals = rng.dirichlet([1.0] * n_bins)
        hypotheses["D"] = {
            k: round(float(v), 4)
            for k, v in zip(true_posterior.keys(), dirichlet_vals)
        }

        # Shuffle hypothesis labels so correct isn't always A
        labels = list(hypotheses.keys())
        dists = [hypotheses[lab] for lab in labels]
        perm = rng.permutation(len(labels))
        shuffled_labels = [chr(ord("A") + i) for i in range(len(labels))]
        shuffled_hypotheses: dict[str, dict[str, float]] = {}
        for new_idx, old_idx in enumerate(perm):
            new_label = shuffled_labels[new_idx]
            shuffled_hypotheses[new_label] = dists[old_idx]
            if labels[old_idx] == "A":
                pass  # correct hypothesis tracked via KL=0

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

    def _causal_effect_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        bin_edges = self._compute_bin_edges(world, target, seed=seed)

        # Use hint if provided and valid
        hint_node = spec.intervention_node
        if hint_node and hint_node in obs_nodes:
            intervention_node = hint_node
        else:
            # Find nodes with causal effect on target
            causal_nodes = []
            for node in obs_nodes:
                if node == target:
                    continue
                node_samples = world.observational_distribution(node, n=5_000, seed=seed)
                lo = float(np.percentile(node_samples, 10))
                hi = float(np.percentile(node_samples, 90))
                do_lo = solver.interventional_samples(target, do={node: lo}, n=5_000, seed=seed)
                do_hi = solver.interventional_samples(target, do={node: hi}, n=5_000, seed=seed)
                diff = abs(float(np.mean(do_hi)) - float(np.mean(do_lo)))
                if diff > 0.1:
                    causal_nodes.append((node, diff))

            if not causal_nodes:
                causal_nodes = [(obs_nodes[0], 0.0)]

            causal_nodes.sort(key=lambda x: x[1], reverse=True)
            weights = np.array([c[1] for c in causal_nodes])
            if weights.sum() > 0:
                weights = weights / weights.sum()
            else:
                weights = np.ones(len(causal_nodes)) / len(causal_nodes)
            chosen_idx = rng.choice(len(causal_nodes), p=weights)
            intervention_node = causal_nodes[chosen_idx][0]

        # Pick an intervention value (75th percentile of marginal).
        # Round BEFORE computing so displayed value matches the answer.
        int_samples = world.observational_distribution(intervention_node, n=5_000, seed=seed)
        int_value = round(float(np.percentile(int_samples, 75)), 2)

        # Compute P(target | do(intervention_node = int_value))
        do_samples = solver.interventional_samples(
            target, do={intervention_node: int_value}, n=50_000, seed=seed
        )
        correct_answer = self._discretize(do_samples, bin_edges)

        remaining = [n for n in obs_nodes if n != intervention_node]
        bins_desc = ", ".join(correct_answer.keys())

        question = (
            f"If '{intervention_node}' were set to {int_value:.2f}, "
            f"what would be the resulting distribution of '{target}' "
            f"across these ranges: {bins_desc}? "
            f"Consider how this change would propagate through the system, "
            f"not just the statistical association in the data."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=remaining,
            correct_answer=correct_answer,
            scoring_method="kl_divergence",
            intervention={intervention_node: f"{int_value:.2f}"},
        )

    def _best_intervention_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)

        # "Desired outcome" for continuous: target above its median
        target_samples = world.observational_distribution(target, n=10_000, seed=seed)
        target_median = float(np.median(target_samples))
        baseline = float(np.mean(target_samples > target_median))  # ~0.5

        # For each observable node, try low (25th) and high (75th) interventions
        intervention_effects: dict[str, float] = {}
        for node_name in obs_nodes:
            if node_name == target:
                continue
            node_samples = world.observational_distribution(node_name, n=5_000, seed=seed)
            lo_val = float(np.percentile(node_samples, 25))
            hi_val = float(np.percentile(node_samples, 75))

            for val, label in [(lo_val, "low"), (hi_val, "high")]:
                do_samples = solver.interventional_samples(
                    target, do={node_name: val}, n=10_000, seed=seed
                )
                effect = float(np.mean(do_samples > target_median))
                intervention_effects[f"{node_name}:{label}"] = round(effect, 6)

        if not intervention_effects:
            intervention_effects["_none_:none"] = round(baseline, 6)

        best_key = max(intervention_effects, key=intervention_effects.get)
        best_node, best_label = best_key.split(":", 1)

        # Build available interventions description
        int_desc_lines = []
        for node_name in obs_nodes:
            if node_name == target:
                continue
            lo_key = f"{node_name}:low"
            if lo_key in intervention_effects:
                int_desc_lines.append(f"  '{node_name}': 'low' or 'high'")

        int_desc = "\n".join(int_desc_lines)
        question = (
            f"You want to maximize the probability of '{target}' being "
            f"above {target_median:.2f} (current baseline: {baseline:.2f}). "
            f"You can change ONE variable by setting it to 'low' or 'high'.\n"
            f"Available interventions:\n{int_desc}\n"
            f"Which variable would you change, and to what level?"
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
            intervention={best_node: best_label},
        )

    def _compare_interventions_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        # Target median for effect computation
        target_samples = world.observational_distribution(target, n=10_000, seed=seed)
        target_median = float(np.median(target_samples))

        # Compute best intervention per node (same as best_intervention)
        node_bests: list[tuple[str, float]] = []
        for node_name in obs_nodes:
            if node_name == target:
                continue
            node_samples = world.observational_distribution(node_name, n=5_000, seed=seed)
            lo_val = float(np.percentile(node_samples, 25))
            hi_val = float(np.percentile(node_samples, 75))

            best_effect = -1.0
            best_key = f"{node_name}:high"
            for val, label in [(lo_val, "low"), (hi_val, "high")]:
                do_samples = solver.interventional_samples(
                    target, do={node_name: val}, n=10_000, seed=seed
                )
                effect = float(np.mean(do_samples > target_median))
                if effect > best_effect:
                    best_effect = effect
                    best_key = f"{node_name}:{label}"

            node_bests.append((best_key, best_effect))

        # Use compare_nodes hint if provided
        used_hint = False
        hint_nodes = spec.compare_nodes
        if hint_nodes and len(hint_nodes) == 2 and len(set(hint_nodes)) == 2:
            node_best_map = {k.split(":")[0]: (k, v) for k, v in node_bests}
            if all(n in node_best_map for n in hint_nodes):
                pick_a = node_best_map[hint_nodes[0]]
                pick_b = node_best_map[hint_nodes[1]]
                used_hint = True

        if not used_hint:
            node_bests.sort(key=lambda e: e[1], reverse=True)
            if len(node_bests) < 2:
                # Not enough nodes to compare
                pick_a = node_bests[0] if node_bests else ("_none_:none", 0.0)
                pick_b = ("_none_:none", 0.0)
            else:
                pick_a = node_bests[0]
                pick_b = node_bests[-1]

        key_a, effect_a = pick_a
        key_b, effect_b = pick_b
        node_a, label_a = key_a.split(":", 1)
        node_b, label_b = key_b.split(":", 1)

        # Randomize presentation order
        if rng.random() < 0.5:
            key_a, effect_a, node_a, label_a, key_b, effect_b, node_b, label_b = (
                key_b, effect_b, node_b, label_b, key_a, effect_a, node_a, label_a,
            )

        correct_answer = {
            key_a: round(effect_a, 6),
            key_b: round(effect_b, 6),
        }

        if effect_a >= effect_b:
            better_node, better_label = node_a, label_a
        else:
            better_node, better_label = node_b, label_b

        question = (
            f"Your team is debating between two possible actions to "
            f"maximize '{target}' being above {target_median:.2f}. "
            f"Option A: set '{node_a}' to '{label_a}'. "
            f"Option B: set '{node_b}' to '{label_b}'. "
            f"Which action would be more effective? Answer 'A' or 'B'."
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
            intervention={better_node: better_label},
        )

    def _should_condition_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        candidates_yes: list[tuple[str, str]] = []
        candidates_no: list[tuple[str, str]] = []

        for x in obs_nodes:
            if x == target:
                continue
            adj_sets = world.get_all_backdoor_adjustment_sets(x, target)
            all_in_sets: set[str] = set()
            for s in adj_sets:
                all_in_sets.update(s)

            desc_of_x = nx.descendants(world.dag, x)

            for z in obs_nodes:
                if z == x or z == target:
                    continue
                if z in all_in_sets:
                    candidates_yes.append((x, z))
                elif z in desc_of_x:
                    candidates_no.append((x, z))

        # Check hints
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
            rng.shuffle(candidates_yes)
            rng.shuffle(candidates_no)

            if candidates_no and candidates_yes:
                ask_no = bool(rng.random() < 0.5)
            elif candidates_no:
                ask_no = True
            elif candidates_yes:
                ask_no = False
            else:
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
            f"You are studying the effect of '{treatment}' on '{target}'. "
            f"A colleague suggests accounting for '{suggested}' in the analysis. "
            f"Is this a good idea, or could it distort the results? "
            f"Answer 'yes' or 'no', and explain your reasoning."
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
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        obs_set = set(obs_nodes)
        rng = np.random.default_rng(seed)

        # Find treatment nodes and classify by identifiability
        candidates = []
        for x in obs_nodes:
            if x == target:
                continue
            adj_sets = world.get_all_backdoor_adjustment_sets(x, target)

            if not adj_sets:
                # Not identifiable
                candidates.append((x, [["_not_identifiable_"]], 0))
                continue

            obs_only_sets = [
                sorted(s) for s in adj_sets if all(v in obs_set for v in s)
            ]

            empty_valid = frozenset() in adj_sets
            has_confounding = not empty_valid

            if has_confounding and obs_only_sets:
                candidates.append((x, obs_only_sets, 3))
            elif has_confounding and not obs_only_sets:
                candidates.append((x, [["_not_identifiable_"]], 0))
            elif not has_confounding:
                candidates.append((x, [[]], 1))

        if not candidates:
            x = obs_nodes[0] if obs_nodes[0] != target else obs_nodes[1]
            candidates = [(x, [[]], 1)]

        # Use hint if provided
        hint_node = spec.intervention_node
        chosen = None
        if hint_node:
            for c in candidates:
                if c[0] == hint_node:
                    chosen = c
                    break

        if chosen is None:
            candidates.sort(key=lambda c: c[2], reverse=True)
            best_priority = candidates[0][2]
            top_candidates = [c for c in candidates if c[2] == best_priority]
            chosen = top_candidates[rng.choice(len(top_candidates))]

        treatment_node = chosen[0]
        valid_sets = chosen[1]

        correct_answer: dict[str, float] = {}
        for s in valid_sets:
            if s == ["_not_identifiable_"]:
                correct_answer["_not_identifiable_"] = 1.0
            elif s:
                correct_answer[",".join(s)] = 1.0
            else:
                correct_answer["_empty_"] = 1.0

        available = [n for n in obs_nodes if n != treatment_node and n != target]

        is_identifiable_confounded = chosen[2] == 3
        is_not_identifiable = "_not_identifiable_" in correct_answer
        if is_identifiable_confounded:
            question = (
                f"You want to estimate the true effect of '{treatment_node}' on "
                f"'{target}' from the data. Some variables may create misleading "
                f"associations if not accounted for. Which variables should you "
                f"include in your analysis to get a fair estimate? "
                f"Available variables: {available}. "
                f"Provide the minimal set needed for an unbiased estimate."
            )
        elif is_not_identifiable:
            question = (
                f"You want to estimate the true effect of '{treatment_node}' on "
                f"'{target}' from the data. "
                f"Available variables: {available}. "
                f"Determine whether this effect can be reliably estimated "
                f"by accounting for available variables, or whether there are "
                f"unmeasured factors that make it impossible."
            )
        else:
            question = (
                f"You want to estimate the true effect of '{treatment_node}' on "
                f"'{target}' from the data. "
                f"Which variables should you account for in your analysis? "
                f"Available variables: {available}. "
                f"If the relationship is already direct, no additional variables "
                f"may be needed."
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

    def _infer_latent_cause_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        obs_nodes = self._obs_nodes(world)
        latent_nodes = sorted(world.latent_variables)
        rng = np.random.default_rng(seed)

        if not latent_nodes:
            raise ValueError(
                "Cannot generate infer_latent_cause task: world has no latent variables"
            )

        latent_node = latent_nodes[rng.choice(len(latent_nodes))]

        # Bin edges for the latent variable
        bin_edges = self._compute_bin_edges(world, latent_node, seed=seed)

        # Sample a true state and give some evidence
        true_state = solver.sample_state(seed=seed)

        max_given = max(1, len(obs_nodes) - 2)
        num_given = int(rng.integers(1, max_given + 1))
        shuffled = list(obs_nodes)
        rng.shuffle(shuffled)
        given_nodes = shuffled[:num_given]

        given_evidence = {n: f"{true_state[n]:.4f}" for n in given_nodes}
        evidence_floats = {n: true_state[n] for n in given_nodes}

        # Compute posterior of latent given evidence
        post_samples = solver.posterior_samples(
            latent_node, evidence=evidence_floats, n=50_000, seed=seed
        )
        correct_answer = self._discretize(post_samples, bin_edges)

        bins_desc = ", ".join(correct_answer.keys())
        evidence_desc = ", ".join(f"'{k}' = {v}" for k, v in given_evidence.items())
        question = (
            f"Based on the observed data ({evidence_desc}), estimate the "
            f"distribution of '{latent_node}' across these ranges: {bins_desc}. "
            f"This factor is not directly measured in the datasets -- you must "
            f"infer it from the available evidence. "
            f"Submit probabilities for each range (summing to 1.0)."
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=latent_node,
            available_evidence=obs_nodes,
            correct_answer=correct_answer,
            scoring_method="kl_divergence",
            given_evidence=given_evidence,
        )


__all__ = ["SCMTaskGenTool"]
