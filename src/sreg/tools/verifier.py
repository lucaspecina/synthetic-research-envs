"""VerifierTool: scores agent performance on episodes."""

from __future__ import annotations

import numpy as np

from sreg.models.score import Score, StepScore


class VerifierTool:
    """Computes scores for agent performance on an episode."""

    def score_hypothesis(
        self,
        agent_choice: str,
        kl_scores: dict[str, float],
    ) -> float:
        """Score a hypothesis_selection answer.

        Returns 1.0 if the agent chose the hypothesis with lowest KL (best match),
        0.0 otherwise.
        """
        if not kl_scores:
            return 0.0
        best_label = min(kl_scores, key=kl_scores.get)
        return 1.0 if agent_choice == best_label else 0.0

    def score_nbo(
        self,
        agent_choice: str,
        ig_ranking: dict[str, float],
    ) -> float:
        """Score a next_best_observation answer.

        Returns the ratio of the agent's chosen node's IG to the optimal IG.
        1.0 = perfect choice, 0.0 = worst possible or invalid choice.
        """
        best_ig = max(ig_ranking.values()) if ig_ranking else 0.0
        if best_ig <= 0:
            # All nodes have zero IG — any choice is equally good
            return 1.0
        agent_ig = ig_ranking.get(agent_choice, 0.0)
        return min(1.0, agent_ig / best_ig)

    def score_best_intervention(
        self,
        agent_node: str,
        agent_state: str,
        intervention_effects: dict[str, float],
    ) -> float:
        """Score a best_intervention answer.

        Returns ratio of agent's intervention effect to optimal effect.
        1.0 = chose the best intervention, 0.0 = invalid choice.
        """
        best_effect = max(intervention_effects.values()) if intervention_effects else 0.0
        if best_effect <= 0:
            return 1.0  # All interventions have zero effect — any choice is fine
        agent_key = f"{agent_node}:{agent_state}"
        agent_effect = intervention_effects.get(agent_key, 0.0)
        return min(1.0, agent_effect / best_effect)

    def score_adjustment_set(
        self,
        agent_set: list[str],
        valid_sets: dict[str, float],
    ) -> float:
        """Score an adjustment_set answer.

        Returns 1.0 if the agent's proposed set matches any valid minimal
        backdoor adjustment set, 0.0 otherwise.
        """
        key = ",".join(sorted(agent_set)) if agent_set else "_empty_"
        return 1.0 if key in valid_sets else 0.0

    def score_compare_interventions(
        self,
        agent_choice: str,
        effects: dict[str, float],
    ) -> float:
        """Score a compare_interventions answer.

        Agent answers 'A' or 'B'. Returns 1.0 if agent picked the intervention
        with higher effect, 0.0 otherwise. If effects are equal, either is correct.
        """
        keys = list(effects.keys())
        if len(keys) != 2:
            return 0.0
        key_a, key_b = keys
        eff_a, eff_b = effects[key_a], effects[key_b]

        # If effects are essentially equal, any answer is correct
        if abs(eff_a - eff_b) < 1e-9:
            return 1.0 if agent_choice in ("A", "B") else 0.0

        correct = "A" if eff_a > eff_b else "B"
        return 1.0 if agent_choice == correct else 0.0

    def score(
        self,
        agent_posterior: dict[str, float],
        true_posterior: dict[str, float],
        per_step_data: list[dict] | None = None,
        budget_used: int = 0,
        budget_total: int = 1,
        max_info_gain: float | None = None,
        achieved_info_gain: float | None = None,
    ) -> Score:
        """Score the agent's final answer and trajectory.

        Args:
            agent_posterior: Agent's submitted distribution over target states.
            true_posterior: True posterior given the same evidence.
            per_step_data: Optional list of dicts with keys:
                step, agent_posterior, true_posterior, cumulative_info_gain.
            budget_used: Number of observations the agent made.
            budget_total: Total observation budget.
            max_info_gain: Maximum possible info gain (teacher's achieved gain).
            achieved_info_gain: Agent's actual info gain.
        """
        functional = self.kl_divergence(agent_posterior, true_posterior)

        efficiency = 0.0
        if max_info_gain is not None and achieved_info_gain is not None and max_info_gain > 0:
            efficiency = min(1.0, achieved_info_gain / max_info_gain)

        per_step: list[StepScore] = []
        if per_step_data:
            for step_data in per_step_data:
                step_kl = self.kl_divergence(
                    step_data["agent_posterior"], step_data["true_posterior"]
                )
                per_step.append(
                    StepScore(
                        step=step_data["step"],
                        posterior_kl=step_kl,
                        cumulative_info_gain=step_data.get("cumulative_info_gain", 0.0),
                        entropy=step_data.get("entropy", 0.0),
                    )
                )

        return Score(
            functional_score=functional,
            information_efficiency=efficiency,
            per_step=per_step,
            budget_used=budget_used,
            budget_total=budget_total,
        )

    @staticmethod
    def kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
        """KL(P || Q) where P is agent, Q is true.

        Uses base-2 logarithm (bits). Adds small epsilon to avoid log(0).
        """
        eps = 1e-10
        states = sorted(set(p.keys()) | set(q.keys()))
        p_vals = np.array([p.get(s, eps) for s in states])
        q_vals = np.array([q.get(s, eps) for s in states])

        # Clip to avoid log(0) and 0*log(0) = NaN
        p_vals = np.clip(p_vals, eps, None)
        q_vals = np.clip(q_vals, eps, None)

        # Normalize
        p_vals = p_vals / p_vals.sum()
        q_vals = q_vals / q_vals.sum()

        return float(np.sum(p_vals * np.log2(p_vals / q_vals)))


__all__ = ["VerifierTool"]
