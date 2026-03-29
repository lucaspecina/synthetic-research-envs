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
import re
from typing import TYPE_CHECKING

import networkx as nx
import numpy as np

from sreg.models.task import Task, TaskBundle, TaskSpec, TaskType
from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld

if TYPE_CHECKING:
    from sreg.models.case_plan import CasePlan, EvalQuestionPlan

logger = logging.getLogger(__name__)


def _kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """KL(P || Q) using base-2 logarithm (bits)."""
    eps = 1e-10
    states = sorted(set(p.keys()) | set(q.keys()))
    p_vals = np.array([p.get(s, eps) for s in states])
    q_vals = np.array([q.get(s, eps) for s in states])
    p_vals = np.clip(p_vals, eps, None)
    q_vals = np.clip(q_vals, eps, None)
    p_vals = p_vals / p_vals.sum()
    q_vals = q_vals / q_vals.sum()
    return float(np.sum(p_vals * np.log2(p_vals / q_vals)))


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

    def generate(
        self,
        world: SCMWorld,
        spec: TaskSpec,
        seed: int = 0,
        treatment_contrasts: dict[str, tuple[float, float]] | None = None,
    ) -> Task:
        """Generate a task from an SCMWorld and specification.

        Parameters
        ----------
        treatment_contrasts : optional mutable cache
            ``{node_name: (v_low, v_high)}``.  When provided, ATE / mediation /
            interaction tasks reuse cached treatment levels for the same node
            (and populate the cache on first use).  This keeps contrasts
            consistent across tasks that share a treatment variable.
        """
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
        if spec.type == TaskType.ATE:
            return self._ate_task(world, spec, seed, treatment_contrasts)
        if spec.type == TaskType.MEDIATION:
            return self._mediation_task(world, spec, seed, treatment_contrasts)
        if spec.type == TaskType.INTERACTION:
            return self._interaction_task(world, spec, seed, treatment_contrasts)
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

    @staticmethod
    def _manipulable_nodes(world: SCMWorld, target: str) -> list[str]:
        """Observable ancestors of *target* — valid intervention levers.

        Excludes downstream outcomes and nodes unrelated to the target.
        A node is manipulable if there is a directed path from it to the
        target in the DAG (i.e., it is a causal ancestor).
        """
        ancestors = nx.ancestors(world.dag, target)
        obs = set(world.observable_variables)
        return sorted(ancestors & obs)

    @staticmethod
    def _semantic_name(world: SCMWorld, node_id: str) -> str:
        """Human-readable name for a variable, suitable for inline use in questions.

        Priority:
        1. variable_meta[node].description if concise (<45 chars AND <=6 words)
        2. node_id with underscores replaced by spaces

        The threshold is intentionally tight: descriptions longer than ~5 words
        produce verbose, mechanical-sounding questions when inserted inline.
        """
        meta = world.variable_meta.get(node_id)
        if meta and meta.description:
            desc = meta.description.rstrip(".")
            if len(desc) < 45 and len(desc.split()) <= 6:
                return desc
        return node_id.replace("_", " ")

    @staticmethod
    def _semantic_aliases(world: SCMWorld, node_id: str) -> set[str]:
        """All valid ways to refer to a variable (for entity matching)."""
        aliases = {node_id.lower(), node_id.replace("_", " ").lower()}
        meta = world.variable_meta.get(node_id)
        if meta and meta.description:
            aliases.add(meta.description.lower())
        return aliases

    @staticmethod
    def _sanitize_question_text(text: str, world: SCMWorld) -> str:
        """Remove snake_case leaks from question text.

        Two passes:
        1. World-aware: replace known node_ids (longest first to avoid
           partial matches) with their space-separated form.
        2. Generic fallback: catch any remaining snake_case tokens that
           aren't known node_ids (e.g. ``p_value``, ``sample_size``).
        """
        # Pass 1: known node_ids, longest first
        all_nodes = sorted(world.dag.nodes, key=len, reverse=True)
        for nid in all_nodes:
            if "_" not in nid:
                continue
            pattern = r"\b" + re.escape(nid) + r"\b"
            text = re.sub(pattern, nid.replace("_", " "), text)

        # Pass 2: generic snake_case tokens (lowercase only, >=2 segments)
        text = re.sub(
            r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b",
            lambda m: m.group(0).replace("_", " "),
            text,
        )
        return text

    def _semantic_evidence_desc(
        self, world: SCMWorld, given_evidence: dict[str, str]
    ) -> str:
        """Format evidence dict using semantic names."""
        parts = []
        for k, v in given_evidence.items():
            name = self._semantic_name(world, k)
            parts.append(f"{name} = {v}")
        return ", ".join(parts)

    def _semantic_node_list(
        self, world: SCMWorld, nodes: list[str]
    ) -> str:
        """Format a list of node IDs as semantic names."""
        return ", ".join(self._semantic_name(world, n) for n in nodes)

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
        target_name = self._semantic_name(world, target)
        question = (
            f"Based on the available data, estimate the distribution of "
            f"{target_name} across these ranges: {bins_desc}. "
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

        evidence_desc = self._semantic_evidence_desc(world, given_evidence)
        remaining_desc = self._semantic_node_list(world, remaining_nodes)
        target_name = self._semantic_name(world, target)
        question = (
            f"You are investigating {target_name}. "
            f"You have already observed: {evidence_desc}. "
            f"You can measure one more variable from: {remaining_desc}. "
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
        kl_scores: dict[str, float] = {}
        for label, dist in shuffled_hypotheses.items():
            kl = _kl_divergence(dist, true_posterior)
            kl_scores[label] = round(kl, 6)

        # Build question text
        evidence_desc = self._semantic_evidence_desc(world, given_evidence)
        target_name = self._semantic_name(world, target)
        hyp_lines = []
        for label, dist in shuffled_hypotheses.items():
            dist_str = ", ".join(f"{s}={p:.2f}" for s, p in dist.items())
            hyp_lines.append(f"  {label}: {dist_str}")
        hyp_text = "\n".join(hyp_lines)

        question = (
            f"You are investigating {target_name}. "
            f"You have observed: {evidence_desc}.\n\n"
            f"Which of these hypotheses best describes the distribution "
            f"of {target_name}?\n"
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
        int_name = self._semantic_name(world, intervention_node)
        target_name = self._semantic_name(world, target)

        question = (
            f"If {int_name} were at {int_value:.2f}, "
            f"what would be the resulting distribution of {target_name} "
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
        lever_nodes = self._manipulable_nodes(world, target)
        if not lever_nodes:
            raise ValueError(
                f"No manipulable ancestors found for target '{target}'"
            )

        # "Desired outcome" for continuous: target above its median
        target_samples = world.observational_distribution(target, n=10_000, seed=seed)
        target_median = float(np.median(target_samples))
        baseline = float(np.mean(target_samples > target_median))  # ~0.5

        # For each manipulable ancestor, try low (25th) and high (75th) interventions
        intervention_effects: dict[str, float] = {}
        for node_name in lever_nodes:
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
        target_name = self._semantic_name(world, target)
        int_desc_lines = []
        for node_name in lever_nodes:
            name = self._semantic_name(world, node_name)
            int_desc_lines.append(f"  {name}: low or high")

        int_desc = "\n".join(int_desc_lines)
        question = (
            f"You want to maximize the probability of {target_name} being "
            f"above {target_median:.2f} (current baseline: {baseline:.2f}). "
            f"You can change one variable to either low or high levels.\n"
            f"Available interventions:\n{int_desc}\n"
            f"Which variable would you change, and to what level?"
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=self._obs_nodes(world),
            correct_answer=intervention_effects,
            scoring_method="intervention_effect_ratio",
            intervention={best_node: best_label},
        )

    def _compare_interventions_task(
        self, world: SCMWorld, spec: TaskSpec, seed: int
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        lever_nodes = self._manipulable_nodes(world, target)
        rng = np.random.default_rng(seed)

        if len(lever_nodes) < 2:
            raise ValueError(
                f"Need at least 2 manipulable ancestors to compare, "
                f"found {len(lever_nodes)} for target '{target}'"
            )

        # Target median for effect computation
        target_samples = world.observational_distribution(target, n=10_000, seed=seed)
        target_median = float(np.median(target_samples))

        # Compute best intervention per manipulable node
        node_bests: list[tuple[str, float]] = []
        for node_name in lever_nodes:
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

        target_name = self._semantic_name(world, target)
        name_a = self._semantic_name(world, node_a)
        name_b = self._semantic_name(world, node_b)
        question = (
            f"Which of these two changes would have a greater impact on "
            f"{target_name}: changing {name_a} to {label_a} levels, or "
            f"changing {name_b} to {label_b} levels?"
        )

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=self._obs_nodes(world),
            correct_answer=correct_answer,
            scoring_method="compare_interventions",
            intervention={better_node: better_label},
            estimand={
                "type": "compare_interventions",
                "option_a": node_a,
                "label_a": label_a,
                "option_b": node_b,
                "label_b": label_b,
                "outcome": target,
            },
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

        treatment_name = self._semantic_name(world, treatment)
        target_name = self._semantic_name(world, target)
        suggested_name = self._semantic_name(world, suggested)
        question = (
            f"You are studying the effect of {treatment_name} on {target_name}. "
            f"A colleague suggests accounting for {suggested_name} in the "
            f"analysis. Is this a good idea, or could it distort the results? "
            f"Explain your reasoning."
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
        treat_name = self._semantic_name(world, treatment_node)
        target_name = self._semantic_name(world, target)
        avail_desc = self._semantic_node_list(world, available)

        is_identifiable_confounded = chosen[2] == 3
        is_not_identifiable = "_not_identifiable_" in correct_answer
        if is_identifiable_confounded:
            question = (
                f"You want to estimate the true effect of {treat_name} on "
                f"{target_name} from the data. Some variables may create "
                f"misleading associations if not accounted for. Which "
                f"variables should you include in your analysis to get a fair "
                f"estimate? Available variables: {avail_desc}. "
                f"Provide the minimal set needed for an unbiased estimate."
            )
        elif is_not_identifiable:
            question = (
                f"You want to estimate the true effect of {treat_name} on "
                f"{target_name} from the data. "
                f"Available variables: {avail_desc}. "
                f"Determine whether this effect can be reliably estimated "
                f"by accounting for available variables, or whether there are "
                f"unmeasured factors that make it impossible."
            )
        else:
            question = (
                f"You want to estimate the true effect of {treat_name} on "
                f"{target_name} from the data. "
                f"Which variables should you account for in your analysis? "
                f"Available variables: {avail_desc}. "
                f"If the relationship is already direct, no additional "
                f"variables may be needed."
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

        # Respect spec.target_node if it's a valid latent variable
        if spec.target_node in world.latent_variables:
            latent_node = spec.target_node
        else:
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
        evidence_desc = self._semantic_evidence_desc(world, given_evidence)
        latent_name = self._semantic_name(world, latent_node)
        _ilc_templates = [
            (
                f"Based on the observed data ({evidence_desc}), estimate the "
                f"distribution of {latent_name} across these ranges: {bins_desc}. "
                f"This factor is not directly measured in the datasets -- you "
                f"must infer it from the available evidence. "
                f"Submit probabilities for each range (summing to 1.0)."
            ),
            (
                f"Given that {evidence_desc}, what is the likely distribution "
                f"of {latent_name}? This variable cannot be observed directly, "
                f"but its effects are visible in the measured data. "
                f"Estimate probabilities across: {bins_desc}."
            ),
            (
                f"The variable {latent_name} is not directly measurable. "
                f"Using the observed values ({evidence_desc}), estimate how "
                f"{latent_name} is distributed across: {bins_desc}. "
                f"Submit a probability distribution (summing to 1.0)."
            ),
        ]
        question = _ilc_templates[int(rng.integers(len(_ilc_templates)))]

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

    # ------------------------------------------------------------------
    # New SCM primitives: ATE, mediation, interaction
    # ------------------------------------------------------------------

    def _ate_task(
        self,
        world: SCMWorld,
        spec: TaskSpec,
        seed: int,
        treatment_contrasts: dict[str, tuple[float, float]] | None = None,
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)

        # Select treatment node
        hint_node = spec.intervention_node
        if hint_node and hint_node in obs_nodes and hint_node != target:
            treatment = hint_node
        else:
            treatment = self._find_best_causal_parent(
                world, solver, target, obs_nodes, seed
            )

        # Treatment levels: 25th and 75th percentile (shared cache)
        v_low, v_high = self._resolve_contrast(
            world, treatment, seed, treatment_contrasts
        )

        ate_value = solver.ate(treatment, target, v_high, v_low, n=50_000, seed=seed)
        correct_answer = {"value": round(ate_value, 4)}

        treat_name = self._semantic_name(world, treatment)
        target_name = self._semantic_name(world, target)
        _ate_templates = [
            (
                f"On average, how much does {target_name} change when "
                f"{treat_name} is higher rather than lower?"
            ),
            (
                f"If {treat_name} were increased from typical low to "
                f"high levels, what average shift would you expect in "
                f"{target_name}?"
            ),
            (
                f"Estimate the average difference in {target_name} "
                f"between lower and higher levels of {treat_name}."
            ),
        ]
        question = _ate_templates[seed % len(_ate_templates)]

        remaining = [n for n in obs_nodes if n != treatment]
        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=remaining,
            correct_answer=correct_answer,
            scoring_method="numeric_relative_error",
            intervention={treatment: f"{v_low:.2f}->{v_high:.2f}"},
            estimand={
                "type": "ate",
                "treatment": treatment,
                "outcome": target,
                "v_low": v_low,
                "v_high": v_high,
            },
        )

    # Mediation fraction outside this range is considered trivial (not interesting).
    _MEDIATION_TRIVIAL_LO = 0.05
    _MEDIATION_TRIVIAL_HI = 0.95

    def _mediation_task(
        self,
        world: SCMWorld,
        spec: TaskSpec,
        seed: int,
        treatment_contrasts: dict[str, tuple[float, float]] | None = None,
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        # Search for non-trivial mediation across multiple treatments
        treatment, mediator, result = self._find_nontrivial_mediation(
            world, solver, spec, target, obs_nodes, seed, rng,
            treatment_contrasts,
        )

        correct_answer = {"value": round(result["fraction_mediated"], 4)}

        # Treatment levels for estimand metadata
        v_low, v_high = self._resolve_contrast(
            world, treatment, seed, treatment_contrasts
        )

        treat_name = self._semantic_name(world, treatment)
        target_name = self._semantic_name(world, target)
        med_name = self._semantic_name(world, mediator)
        _med_templates = [
            (
                f"Does {treat_name} affect {target_name} partly through "
                f"{med_name}? Roughly how much of the effect seems to "
                f"run through that pathway?"
            ),
            (
                f"If {treat_name} influences {target_name}, is {med_name} "
                f"one of the main routes? Estimate how important that "
                f"indirect pathway is."
            ),
            (
                f"How much of the relationship between {treat_name} and "
                f"{target_name} can be explained by changes in "
                f"{med_name}?"
            ),
        ]
        question = _med_templates[seed % len(_med_templates)]

        remaining = [n for n in obs_nodes if n != treatment]
        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=remaining,
            correct_answer=correct_answer,
            scoring_method="numeric_relative_error",
            intervention={treatment: mediator},
            estimand={
                "type": "mediation",
                "treatment": treatment,
                "mediator": mediator,
                "outcome": target,
                "v_low": v_low,
                "v_high": v_high,
            },
        )

    def _interaction_task(
        self,
        world: SCMWorld,
        spec: TaskSpec,
        seed: int,
        treatment_contrasts: dict[str, tuple[float, float]] | None = None,
    ) -> Task:
        solver = SCMSolver(world)
        target = spec.target_node
        obs_nodes = self._obs_nodes(world)
        rng = np.random.default_rng(seed)

        # Try hinted pair first, then search for a pair with real interaction
        treatment, modifier, v_low, v_high, result = self._find_interacting_pair(
            world, solver, spec, target, obs_nodes, seed, rng, treatment_contrasts
        )

        correct_answer = (
            {"yes": 1.0} if result["interaction_detected"] else {"no": 1.0}
        )

        treat_name = self._semantic_name(world, treatment)
        target_name = self._semantic_name(world, target)
        mod_name = self._semantic_name(world, modifier)
        _int_templates = [
            (
                f"Does {mod_name} change how much {treat_name} matters "
                f"for {target_name}?"
            ),
            (
                f"Is the effect of {treat_name} on {target_name} "
                f"stronger or weaker depending on {mod_name}?"
            ),
            (
                f"Does the impact of {treat_name} on {target_name} "
                f"differ across levels of {mod_name}?"
            ),
        ]
        question = _int_templates[seed % len(_int_templates)]

        return Task(
            id=f"task-{world.id}-{spec.type}",
            type=spec.type,
            world_id=world.id,
            question=question,
            target_node=target,
            available_evidence=obs_nodes,
            correct_answer=correct_answer,
            scoring_method="should_condition",
            intervention={treatment: modifier},
            estimand={
                "type": "interaction",
                "treatment": treatment,
                "modifier": modifier,
                "outcome": target,
                "v_low": v_low,
                "v_high": v_high,
            },
        )

    # ------------------------------------------------------------------
    # Helpers for new primitives
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_contrast(
        world: SCMWorld,
        treatment: str,
        seed: int,
        cache: dict[str, tuple[float, float]] | None = None,
    ) -> tuple[float, float]:
        """Return (v_low, v_high) for a treatment, using cache when available."""
        if cache is not None and treatment in cache:
            return cache[treatment]
        t_samples = world.observational_distribution(treatment, n=10_000, seed=seed)
        v_low = round(float(np.percentile(t_samples, 25)), 2)
        v_high = round(float(np.percentile(t_samples, 75)), 2)
        if cache is not None:
            cache[treatment] = (v_low, v_high)
        return v_low, v_high

    @staticmethod
    def _find_best_causal_parent(
        world: SCMWorld,
        solver: SCMSolver,
        target: str,
        obs_nodes: list[str],
        seed: int,
    ) -> str:
        """Find observable node with strongest causal effect on target."""
        best_node = obs_nodes[0] if obs_nodes[0] != target else obs_nodes[1]
        best_effect = 0.0
        for node in obs_nodes:
            if node == target:
                continue
            node_samples = world.observational_distribution(node, n=5_000, seed=seed)
            lo = float(np.percentile(node_samples, 25))
            hi = float(np.percentile(node_samples, 75))
            do_lo = solver.interventional_samples(
                target, do={node: lo}, n=5_000, seed=seed
            )
            do_hi = solver.interventional_samples(
                target, do={node: hi}, n=5_000, seed=seed
            )
            effect = abs(float(np.mean(do_hi)) - float(np.mean(do_lo)))
            if effect > best_effect:
                best_effect = effect
                best_node = node
        return best_node

    @staticmethod
    def _find_mediator(
        world: SCMWorld,
        treatment: str,
        outcome: str,
        obs_nodes: list[str],
        rng: np.random.Generator,
    ) -> str | None:
        """Find a node on a directed path from treatment to outcome."""
        dag = world.dag
        try:
            paths = list(nx.all_simple_paths(dag, treatment, outcome))
        except nx.NetworkXError:
            return None
        intermediates = set()
        for path in paths:
            for node in path[1:-1]:
                if node in obs_nodes:
                    intermediates.add(node)
        if not intermediates:
            return None
        candidates = sorted(intermediates)
        return candidates[rng.choice(len(candidates))]

    def _find_nontrivial_mediation(
        self,
        world: SCMWorld,
        solver: SCMSolver,
        spec: TaskSpec,
        target: str,
        obs_nodes: list[str],
        seed: int,
        rng: np.random.Generator,
        treatment_contrasts: dict[str, tuple[float, float]] | None = None,
    ) -> tuple[str, str, dict]:
        """Find a (treatment, mediator) pair with non-trivial mediation.

        Non-trivial means fraction_mediated is in
        (_MEDIATION_TRIVIAL_LO, _MEDIATION_TRIVIAL_HI).

        Explores multiple treatments (hinted first, then best causal
        parent, then all observable ancestors with mediators).  For each
        treatment, tries hinted mediator first, then all intermediates.

        Raises ValueError if all pairs are trivial.

        Returns (treatment, mediator, mediation_result).
        """
        lo = self._MEDIATION_TRIVIAL_LO
        hi = self._MEDIATION_TRIVIAL_HI
        obs_set = set(obs_nodes)
        dag = world.dag

        # Build ordered treatment list: hint > best_parent > ancestors
        treatments: list[str] = []
        hint_t = spec.intervention_node
        if hint_t and hint_t in obs_set and hint_t != target:
            treatments.append(hint_t)
        best_parent = self._find_best_causal_parent(
            world, solver, target, obs_nodes, seed
        )
        if best_parent and best_parent not in treatments:
            treatments.append(best_parent)
        ancestors = nx.ancestors(dag, target) & obs_set
        for p in sorted(ancestors):
            if p not in treatments:
                treatments.append(p)

        hint_mediator = spec.condition_variable
        best_result = None
        best_mediator = None
        best_treatment = None
        best_distance = 1.0

        for treatment in treatments:
            v_low, v_high = self._resolve_contrast(
                world, treatment, seed, treatment_contrasts
            )

            # Build mediator candidates for this treatment
            candidates: list[str] = []
            if (
                hint_mediator
                and hint_mediator in obs_set
                and hint_mediator != treatment
                and hint_mediator != target
            ):
                candidates.append(hint_mediator)
            try:
                paths = list(nx.all_simple_paths(dag, treatment, target))
            except nx.NetworkXError:
                paths = []
            for path in paths:
                for node in path[1:-1]:
                    if node in obs_set and node not in candidates:
                        candidates.append(node)

            for mediator in candidates:
                result = solver.mediation_analysis(
                    treatment, mediator, target, v_high, v_low,
                    n=20_000, seed=seed,
                )
                frac = result["fraction_mediated"]
                if lo < frac < hi:
                    return treatment, mediator, result
                dist = min(abs(frac - lo), abs(frac - hi))
                if dist < best_distance:
                    best_distance = dist
                    best_result = result
                    best_mediator = mediator
                    best_treatment = treatment

        if best_result is None:
            raise ValueError(
                f"No mediator found for any treatment -> '{target}'"
            )
        raise ValueError(
            f"All mediators for '{target}' have trivial "
            f"fraction_mediated (outside {lo}-{hi}). Best was "
            f"'{best_treatment}' -> '{best_mediator}' = "
            f"{best_result['fraction_mediated']:.3f}. "
            f"Skipping mediation task."
        )

    @staticmethod
    def _find_modifier(
        world: SCMWorld,
        treatment: str,
        outcome: str,
        obs_nodes: list[str],
        rng: np.random.Generator,
    ) -> str | None:
        """Find a node suitable as effect modifier (not on treatment->outcome path)."""
        dag = world.dag
        try:
            paths = list(nx.all_simple_paths(dag, treatment, outcome))
        except nx.NetworkXError:
            paths = []
        path_nodes = set()
        for path in paths:
            path_nodes.update(path)

        candidates = [
            n for n in obs_nodes
            if n != treatment and n != outcome and n not in path_nodes
        ]
        # Prefer parents of outcome
        outcome_parents = set(dag.predecessors(outcome))
        preferred = [n for n in candidates if n in outcome_parents]
        pool = preferred if preferred else candidates
        if not pool:
            return None
        pool_sorted = sorted(pool)
        return pool_sorted[rng.choice(len(pool_sorted))]

    def _find_interacting_pair(
        self,
        world: SCMWorld,
        solver: SCMSolver,
        spec: TaskSpec,
        target: str,
        obs_nodes: list[str],
        seed: int,
        rng: np.random.Generator,
        treatment_contrasts: dict[str, tuple[float, float]] | None = None,
    ) -> tuple[str, str, float, float, dict]:
        """Search for a (treatment, modifier) pair, preferring real interactions.

        Explores all observable ancestors of *target* as candidate treatments
        (hinted first, then best causal parent, then remaining ancestors).
        For each treatment, tries all valid modifiers.

        If a pair with ``interaction_detected=True`` is found, returns it
        immediately (answer will be "yes").  Otherwise returns the pair with
        the highest ``relative_range`` (answer will be "no") so that
        interaction tasks have a natural mix of yes/no outcomes.

        Returns (treatment, modifier, v_low, v_high, detect_result).
        """
        obs_set = set(obs_nodes)
        ancestors = nx.ancestors(world.dag, target) & obs_set

        # Build ordered treatment list: hint > best_parent > all ancestors
        treatments: list[str] = []
        hint_t = spec.intervention_node
        if hint_t and hint_t in ancestors:
            treatments.append(hint_t)
        best_parent = self._find_best_causal_parent(
            world, solver, target, obs_nodes, seed
        )
        if best_parent and best_parent not in treatments and best_parent in ancestors:
            treatments.append(best_parent)
        for p in sorted(ancestors):
            if p not in treatments:
                treatments.append(p)

        if not treatments:
            raise ValueError(
                f"No observable ancestors for interaction search on '{target}'"
            )

        best_yes: tuple[str, str, float, float, dict] | None = None
        best_yes_range = -1.0
        best_no: tuple[str, str, float, float, dict] | None = None
        best_no_range = -1.0

        for treatment in treatments:
            v_low, v_high = self._resolve_contrast(
                world, treatment, seed, treatment_contrasts
            )

            # Build modifier candidates: hint first, then _find_modifier pool
            modifiers: list[str] = []
            hint_m = spec.condition_variable
            if (
                hint_m
                and hint_m in obs_set
                and hint_m != treatment
                and hint_m != target
            ):
                modifiers.append(hint_m)

            dag = world.dag
            try:
                paths = list(nx.all_simple_paths(dag, treatment, target))
            except nx.NetworkXError:
                paths = []
            path_nodes = set()
            for path in paths:
                path_nodes.update(path)
            candidates = sorted(
                n for n in obs_nodes
                if n != treatment and n != target and n not in path_nodes
                and n not in modifiers
            )
            modifiers.extend(candidates)

            for modifier in modifiers:
                result = solver.detect_interaction(
                    treatment, target, modifier, v_high, v_low,
                    n=50_000, seed=seed,
                )
                rr = result.get("relative_range", 0.0)
                if result["interaction_detected"]:
                    # Track strongest "yes" (don't return first — may be FP)
                    if rr > best_yes_range:
                        best_yes_range = rr
                        best_yes = (treatment, modifier, v_low, v_high, result)
                else:
                    if rr > best_no_range:
                        best_no_range = rr
                        best_no = (treatment, modifier, v_low, v_high, result)

        # Prefer strongest "yes", fall back to best "no"
        if best_yes is not None:
            return best_yes
        if best_no is not None:
            return best_no

        raise ValueError(
            f"No valid treatment/modifier pairs found for '{target}'"
        )

    # ------------------------------------------------------------------
    # Plan-driven generation
    # ------------------------------------------------------------------

    # Types where overriding the question risks semantic inversion
    # (e.g. answer encodes specific node labels that must appear verbatim).
    # Currently empty — all types use hint-based gating instead.
    _NEVER_OVERRIDE_QUESTION_TYPES: frozenset[TaskType] = frozenset()

    def generate_from_plan(
        self,
        world: SCMWorld,
        plan: CasePlan,
        seed: int = 0,
    ) -> list[Task]:
        """Generate tasks driven by a CasePlan.

        Mirrors TaskGenTool.generate_from_plan() but for continuous SCMWorld.
        Node hints in the plan are passed through to the task generator.

        Question text override rules:
        - "Safe" types (infer_target, NBO, hypothesis, infer_latent_cause):
          always override with plan's question_text.
        - Other types: override ONLY when hints were honored.
        """
        tasks: list[Task] = []
        errors: list[str] = []
        # Shared contrast cache: same treatment → same (v_low, v_high)
        contrast_cache: dict[str, tuple[float, float]] = {}

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
            try:
                task = self.generate(
                    world, spec, seed=seed + i,
                    treatment_contrasts=contrast_cache,
                )
            except Exception as e:
                logger.warning(
                    "Skipping question %d (%s): %s", i + 1, q.eval_type, e
                )
                errors.append(f"Q{i + 1} ({q.eval_type}): {e}")
                continue

            # Decide whether to override the auto-generated question text.
            # Gate: structural hints (intervention_node, condition_variable)
            # are the authority — entity matching is telemetry, not a gate.
            if q.eval_type in self._NEVER_OVERRIDE_QUESTION_TYPES:
                pass
            elif self._hints_honored(q, task):
                # Structural bindings match → trust orchestrator's question.
                # Entity matching is informational only.
                if task.estimand and not self._entities_match_question(
                    q.question_text, task, world=world
                ):
                    logger.info(
                        "Entity match failed but hints honored for %s — "
                        "using orchestrator question. (question: '%.80s...')",
                        q.eval_type.value, q.question_text,
                    )
                task = task.model_copy(update={"question": q.question_text})
            elif not task.estimand:
                # Non-estimand types (infer_target, hypothesis_selection,
                # infer_latent_cause, nbo) — always safe to override.
                task = task.model_copy(update={"question": q.question_text})
            else:
                # Has estimand but hints not honored → keep generated
                # question to avoid semantic mismatch.
                logger.warning(
                    "Question override rejected for %s: structural hints "
                    "not honored. Keeping generated question. "
                    "(question: '%.80s...', estimand: %s)",
                    q.eval_type.value, q.question_text, task.estimand,
                )

            # Sanitize snake_case leaks from both override and auto-template paths
            clean_q = self._sanitize_question_text(task.question, world)
            if clean_q != task.question:
                task = task.model_copy(update={"question": clean_q})

            self._check_question_answer_consistency(task, q.eval_type, world=world)
            tasks.append(task)

        if not tasks:
            raise ValueError(
                f"All questions failed to generate: {'; '.join(errors)}"
            )
        if errors:
            logger.warning(
                "Generated %d/%d tasks (%d skipped)",
                len(tasks), len(plan.questions), len(errors),
            )
        return tasks

    @staticmethod
    def _check_question_answer_consistency(
        task: Task, eval_type: TaskType, world: SCMWorld | None = None
    ) -> None:
        """Log a warning if the question text doesn't mention nodes from the answer.

        Checks against all semantic aliases (node_id, spaces version,
        variable_meta description) when world is available.
        """
        if not task.correct_answer or not task.question:
            return

        question_lower = task.question.lower()
        nodes_to_check: list[str] = []

        if eval_type in (
            TaskType.CAUSAL_EFFECT, TaskType.ADJUSTMENT_SET,
            TaskType.SHOULD_CONDITION, TaskType.ATE,
            TaskType.MEDIATION, TaskType.INTERACTION,
        ):
            if task.intervention:
                nodes_to_check = list(task.intervention.keys())
        elif eval_type == TaskType.COMPARE_INTERVENTIONS:
            nodes_to_check = [k.split(":")[0] for k in task.correct_answer]
        elif eval_type == TaskType.BEST_INTERVENTION:
            return
        else:
            return

        def _found(node_id: str) -> bool:
            if world:
                aliases = SCMTaskGenTool._semantic_aliases(world, node_id)
                return any(a in question_lower for a in aliases)
            return node_id.lower() in question_lower

        missing = [n for n in nodes_to_check if not _found(n)]
        if missing:
            logger.warning(
                "Question/answer consistency: task %s (%s) -- question does not "
                "mention nodes from the answer: %s. Question: '%.80s...'",
                task.id, eval_type.value, missing, task.question,
            )

    @staticmethod
    def _hints_honored(q: EvalQuestionPlan, task: Task) -> bool:
        """Check whether the generated task actually used the plan's hints."""
        et = q.eval_type
        inv = task.intervention

        if et == TaskType.CAUSAL_EFFECT:
            return bool(q.intervention_node and q.intervention_node in inv)

        if et == TaskType.BEST_INTERVENTION:
            # No structural hints required — target_node is always honored
            # via spec. The orchestrator's question is always acceptable.
            return True

        if et == TaskType.COMPARE_INTERVENTIONS:
            if not q.compare_nodes or len(q.compare_nodes) != 2:
                return False
            if len(set(q.compare_nodes)) != 2:
                return False
            answer_nodes = {k.split(":")[0] for k in task.correct_answer}
            return set(q.compare_nodes) == answer_nodes

        if et == TaskType.ADJUSTMENT_SET:
            return bool(q.intervention_node and q.intervention_node in inv)

        if et == TaskType.SHOULD_CONDITION:
            if not (q.intervention_node and q.condition_variable):
                return False
            return inv == {q.intervention_node: q.condition_variable}

        if et == TaskType.ATE:
            return bool(q.intervention_node and q.intervention_node in inv)

        if et == TaskType.MEDIATION:
            if not (q.intervention_node and q.condition_variable):
                return False
            est = task.estimand or {}
            return (
                est.get("treatment") == q.intervention_node
                and est.get("mediator") == q.condition_variable
            )

        if et == TaskType.INTERACTION:
            if not (q.intervention_node and q.condition_variable):
                return False
            est = task.estimand or {}
            return (
                est.get("treatment") == q.intervention_node
                and est.get("modifier") == q.condition_variable
            )

        return False

    @staticmethod
    def _entities_match_question(
        question_text: str, task: Task, world: SCMWorld | None = None
    ) -> bool:
        """Check whether key estimand entities appear in the question text.

        For ATE the treatment must appear; for mediation the treatment AND
        mediator; for interaction the treatment AND modifier.  Names are
        matched against all semantic aliases (node_id, spaces version,
        variable_meta description).  Returns True for types without an
        estimand.
        """
        if not task.estimand or not question_text:
            return True

        q_lower = question_text.lower()

        def _present(name: str | float) -> bool:
            if not isinstance(name, str):
                return True
            # Check all semantic aliases if world is available
            if world:
                aliases = SCMTaskGenTool._semantic_aliases(world, name)
                return any(a in q_lower for a in aliases)
            return (
                name.lower() in q_lower
                or name.replace("_", " ").lower() in q_lower
            )

        etype = task.estimand.get("type", "")
        if etype == "ate":
            return _present(task.estimand.get("treatment", ""))
        if etype == "mediation":
            return _present(task.estimand.get("treatment", "")) and _present(
                task.estimand.get("mediator", "")
            )
        if etype == "interaction":
            return _present(task.estimand.get("treatment", "")) and _present(
                task.estimand.get("modifier", "")
            )
        if etype == "compare_interventions":
            return (
                _present(task.estimand.get("option_a", ""))
                and _present(task.estimand.get("option_b", ""))
                and _present(task.estimand.get("outcome", ""))
            )
        return True


__all__ = ["SCMTaskGenTool"]
