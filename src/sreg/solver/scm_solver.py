"""Monte Carlo teacher solver for SCMWorld.

Replaces ExactBayesSolver for continuous/SCM worlds. Uses sampling
instead of exact pgmpy inference. Results are approximate but work
with arbitrary equations (nonlinear, threshold, interaction, etc.).

Key differences from ExactBayesSolver:
- Distributions are represented as sample arrays (np.ndarray), not dicts.
- Posteriors given evidence use rejection sampling with adaptive tolerance.
- Information gain is estimated via binned mutual information.
- TeacherOutput.posterior is empty dict (continuous has no discrete states).
- Entropy is in bits (log2), consistent with ExactBayesSolver.

Known limitations (to address when integrating with pipeline):
- Rejection sampling scales poorly with many evidence variables (>5).
  Future: switch to importance weighting with ESS monitoring.
- TeacherOutput.posterior is empty — callers needing distributions
  should use posterior_samples() / interventional_samples() directly.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from sreg.models.episode import Action, ActionType
from sreg.models.teacher import TeacherOutput
from sreg.world.scm import SCMWorld

logger = logging.getLogger(__name__)


class SCMSolver:
    """Monte Carlo inference engine for SCMWorld.

    Plays the role of teacher (optimal policy) -- computes posteriors,
    interventional distributions, and information gain via sampling.

    Mirrors ExactBayesSolver's role but uses Monte Carlo estimation.
    """

    def __init__(self, world: SCMWorld, n_mc: int = 100_000):
        """Initialize the solver.

        Args:
            world: The SCMWorld to solve.
            n_mc: Default Monte Carlo sample count for distribution estimates.
        """
        self.world = world
        self.n_mc = n_mc

    def sample_state(self, seed: int | None = None) -> dict[str, float]:
        """Sample a complete world state from the joint distribution."""
        rng = np.random.default_rng(seed)
        return self.world._sample_one(rng)

    def posterior_samples(
        self,
        target: str,
        evidence: dict[str, float] | None = None,
        n: int = 10_000,
        seed: int | None = None,
    ) -> np.ndarray:
        """Estimate P(target | evidence) via rejection sampling.

        Args:
            target: Variable to get the distribution of.
            evidence: Observed values {variable: value}. None returns marginal.
            n: Desired number of output samples.
            seed: Random seed.

        Returns:
            1D array of samples from the conditional distribution.

        Raises:
            ValueError: If target or evidence variables don't exist in the world.
        """
        self._validate_variables(target, evidence)

        if not evidence:
            return self.world.observational_distribution(target, n=n, seed=seed)

        oversample = min(n * 50, self.n_mc)
        df = self.world.sample(n=oversample, seed=seed)
        matched = self._rejection_filter(df, evidence)

        if len(matched) == 0:
            logger.warning(
                "Rejection sampling found 0 matches for evidence %s. "
                "Returning marginal P(%s) as fallback — this is NOT the "
                "true posterior. Consider increasing n_mc or checking "
                "evidence values.",
                evidence,
                target,
            )
            return self.world.observational_distribution(target, n=n, seed=seed)

        if len(matched) < 50:
            logger.warning(
                "Rejection sampling found only %d matches (< 50) for "
                "evidence %s. Posterior estimate may be unreliable.",
                len(matched),
                evidence,
            )

        result = matched[target].values
        if len(result) > n:
            rng = np.random.default_rng(seed)
            result = rng.choice(result, size=n, replace=False)

        return result

    def interventional_samples(
        self,
        target: str,
        do: dict[str, float],
        evidence: dict[str, float] | None = None,
        n: int = 10_000,
        seed: int | None = None,
    ) -> np.ndarray:
        """Estimate P(target | do(interventions), evidence) via sampling.

        Args:
            target: Variable to get the distribution of.
            do: Interventions {variable: fixed_value}.
            evidence: Additional conditioning (after intervention).
            n: Desired number of output samples.
            seed: Random seed.

        Returns:
            1D array of samples from the interventional distribution.

        Raises:
            ValueError: If any variable doesn't exist in the world.
        """
        all_vars = {target} | set(do.keys()) | set((evidence or {}).keys())
        unknown = all_vars - set(self.world.variables)
        if unknown:
            raise ValueError(f"Unknown variables: {unknown}")

        if not evidence:
            return self.world.interventional_distribution(target, do, n=n, seed=seed)

        oversample = min(n * 50, self.n_mc)
        df = self.world.sample(n=oversample, seed=seed, do=do)

        # Don't filter on intervened variables
        filter_evidence = {k: v for k, v in evidence.items() if k not in do}
        if not filter_evidence:
            result = df[target].values
            if len(result) > n:
                rng = np.random.default_rng(seed)
                result = rng.choice(result, size=n, replace=False)
            return result

        matched = self._rejection_filter(df, filter_evidence)
        if len(matched) == 0:
            logger.warning(
                "Rejection found 0 matches for interventional evidence %s. "
                "Returning P(%s | do(%s)) without conditioning.",
                filter_evidence,
                target,
                do,
            )
            return self.world.interventional_distribution(target, do, n=n, seed=seed)

        result = matched[target].values
        if len(result) > n:
            rng = np.random.default_rng(seed)
            result = rng.choice(result, size=n, replace=False)

        return result

    def entropy(
        self,
        samples: np.ndarray,
        bins: int = 50,
        bin_edges: np.ndarray | None = None,
    ) -> float:
        """Estimate entropy from samples via histogram.

        Uses binned distribution, so entropy is always non-negative.

        Args:
            samples: 1D array of samples.
            bins: Number of histogram bins (ignored if bin_edges provided).
            bin_edges: Fixed bin edges. When provided, ensures entropy is
                computed on a consistent scale (critical for IG computation).

        Returns:
            Entropy in bits (log2). Always >= 0.
        """
        if len(samples) < 2:
            return 0.0

        if bin_edges is not None:
            hist, _ = np.histogram(samples, bins=bin_edges, density=False)
        else:
            hist, _ = np.histogram(samples, bins=bins, density=False)
        probs = hist / hist.sum()
        pos = probs > 0
        return float(-np.sum(probs[pos] * np.log2(probs[pos])))

    def information_gain(
        self,
        target: str,
        evidence: dict[str, float],
        candidate: str,
        n: int = 50_000,
        n_bins: int = 20,
        seed: int | None = None,
    ) -> float:
        """Expected information gain from observing candidate variable.

        IG = H(target | evidence) - E_x[H(target | evidence, candidate=x)]

        Estimated by binning the candidate variable and computing
        conditional entropy in each bin. Bins with too few samples
        are assumed to contribute prior entropy (conservative estimate).
        """
        self._validate_variables(target, evidence, candidate)

        df = self._get_joint_samples(evidence, n=n, seed=seed)
        if len(df) < 50:
            return 0.0

        igs = self._compute_ig_from_df(df, target, [candidate], n_bins=n_bins)
        return igs[candidate]

    def optimal_action(
        self,
        target: str,
        evidence: dict[str, float],
        available: list[str],
        costs: dict[str, int] | None = None,
        seed: int | None = None,
    ) -> TeacherOutput:
        """Select the observation that maximizes information gain per cost.

        Args:
            target: Target variable.
            evidence: Current observations.
            available: Candidate variables to observe.
            costs: Cost per variable. Default: all cost 1.
            seed: Random seed.

        Returns:
            TeacherOutput with recommendation and entropy info.
            posterior field is empty (use posterior_samples() for distributions).
        """
        # Use shared joint samples for both entropy and IG (consistency)
        df = self._get_joint_samples(evidence, n=50_000, seed=seed)
        if len(df) < 50:
            return TeacherOutput(
                posterior={},
                recommended_action=None,
                information_gain=0.0,
                entropy=0.0,
            )

        # Fixed target bins — used for both current_h and IG
        target_bin_edges = self._target_bin_edges(df[target].values)
        current_h = self.entropy(df[target].values, bin_edges=target_bin_edges)

        if not available or current_h < 1e-6:
            return TeacherOutput(
                posterior={},
                recommended_action=None,
                information_gain=0.0,
                entropy=current_h,
            )

        igs = self._compute_ig_from_df(df, target, available)

        best_score = -1.0
        best_node = None
        best_gain = 0.0

        for node in available:
            gain = igs.get(node, 0.0)
            cost = costs.get(node, 1) if costs else 1
            score = gain / cost if cost > 0 else 0.0
            if score > best_score:
                best_score = score
                best_node = node
                best_gain = gain

        return TeacherOutput(
            posterior={},
            recommended_action=Action(type=ActionType.OBSERVE, node=best_node),
            information_gain=max(0.0, best_gain),
            entropy=current_h,
        )

    def generate_trajectory(
        self,
        target: str,
        available: list[str],
        budget: int,
        seed: int | None = None,
        costs: dict[str, int] | None = None,
    ) -> tuple[dict[str, float], list[TeacherOutput]]:
        """Generate an optimal trajectory for a sampled world state.

        Returns:
            (true_state, trajectory) where trajectory is a sequence of TeacherOutputs.
        """
        true_state = self.sample_state(seed)

        evidence: dict[str, float] = {}
        remaining = list(available)
        trajectory: list[TeacherOutput] = []
        budget_left = budget

        for step in range(budget):
            if not remaining:
                break

            affordable = [
                n for n in remaining
                if (costs.get(n, 1) if costs else 1) <= budget_left
            ]
            if not affordable:
                break

            step_seed = (seed or 0) + step * 100_003
            output = self.optimal_action(
                target, evidence, affordable, costs=costs, seed=step_seed
            )
            trajectory.append(output)

            if output.recommended_action is None:
                break

            node = output.recommended_action.node
            cost = costs.get(node, 1) if costs else 1
            budget_left -= cost
            evidence[node] = true_state[node]
            remaining.remove(node)

        # Final posterior entropy — use fixed bins from fresh joint samples
        final_df = self._get_joint_samples(evidence, n=50_000, seed=seed)
        if len(final_df) > 0:
            final_bin_edges = self._target_bin_edges(final_df[target].values)
            final_h = self.entropy(final_df[target].values, bin_edges=final_bin_edges)
        else:
            final_h = 0.0

        trajectory.append(
            TeacherOutput(
                posterior={},
                recommended_action=None,
                information_gain=0.0,
                entropy=final_h,
            )
        )

        return true_state, trajectory

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_variables(
        self, target: str, evidence: dict[str, float] | None = None, *extra: str
    ) -> None:
        """Raise ValueError if any variable doesn't exist in the world."""
        all_vars = {target} | set((evidence or {}).keys()) | set(extra)
        unknown = all_vars - set(self.world.variables)
        if unknown:
            raise ValueError(f"Unknown variables: {unknown}")

    def _target_bin_edges(
        self, target_vals: np.ndarray, n_bins: int = 50
    ) -> np.ndarray:
        """Compute fixed bin edges for target variable."""
        t_min, t_max = target_vals.min(), target_vals.max()
        t_range = t_max - t_min
        if t_range < 1e-10:
            return np.array([t_min - 1, t_max + 1])
        return np.linspace(
            t_min - 0.01 * t_range, t_max + 0.01 * t_range, n_bins + 1
        )

    def _get_joint_samples(
        self,
        evidence: dict[str, float] | None,
        n: int = 50_000,
        seed: int | None = None,
    ) -> pd.DataFrame:
        """Get joint samples optionally filtered by evidence."""
        if evidence:
            oversample = min(n * 50, self.n_mc * 5)
            df = self.world.sample(n=oversample, seed=seed)
            return self._rejection_filter(df, evidence)
        return self.world.sample(n=n, seed=seed)

    def _compute_ig_from_df(
        self,
        df: pd.DataFrame,
        target: str,
        candidates: list[str],
        n_bins: int = 20,
        target_entropy_bins: int = 50,
    ) -> dict[str, float]:
        """Compute information gain for multiple candidates from shared samples.

        Uses FIXED bin edges for target entropy — critical for correct IG.
        Bins with too few samples (<5) are conservatively assumed to have
        prior entropy (i.e., no information gained for those observations).
        """
        target_vals = df[target].values
        total = len(df)

        target_bin_edges = self._target_bin_edges(target_vals, target_entropy_bins)
        h_prior = self.entropy(target_vals, bin_edges=target_bin_edges)

        results: dict[str, float] = {}
        for candidate in candidates:
            if candidate not in df.columns:
                results[candidate] = 0.0
                continue

            candidate_vals = df[candidate].values

            # Equal-count bins via percentiles for the candidate variable
            bin_edges = np.percentile(candidate_vals, np.linspace(0, 100, n_bins + 1))
            bin_edges = np.unique(bin_edges)
            if len(bin_edges) < 2:
                results[candidate] = 0.0
                continue

            expected_h = 0.0
            accounted_weight = 0.0
            for i in range(len(bin_edges) - 1):
                lo, hi = bin_edges[i], bin_edges[i + 1]
                if i == len(bin_edges) - 2:
                    bin_mask = (candidate_vals >= lo) & (candidate_vals <= hi)
                else:
                    bin_mask = (candidate_vals >= lo) & (candidate_vals < hi)

                bin_targets = target_vals[bin_mask]
                if len(bin_targets) < 5:
                    continue

                weight = len(bin_targets) / total
                accounted_weight += weight
                expected_h += weight * self.entropy(
                    bin_targets, bin_edges=target_bin_edges
                )

            # Unaccounted weight: assume no info gained (conservative)
            if accounted_weight > 0:
                unaccounted = 1.0 - accounted_weight
                expected_h += unaccounted * h_prior
            else:
                expected_h = h_prior

            results[candidate] = max(0.0, h_prior - expected_h)

        return results

    def _rejection_filter(
        self,
        df: pd.DataFrame,
        evidence: dict[str, float],
        initial_tol_fraction: float = 0.1,
        max_widen: int = 5,
        widen_factor: float = 1.5,
        min_samples: int = 100,
    ) -> pd.DataFrame:
        """Filter DataFrame rows to approximately match evidence values.

        Uses tolerance bands around each evidence value (fraction of std).
        Widens tolerance progressively if too few matches found.
        """
        last_matched = df.iloc[:0]  # empty with same columns

        for attempt in range(max_widen + 1):
            factor = widen_factor ** attempt
            mask = pd.Series(True, index=df.index)

            for var, val in evidence.items():
                if var not in df.columns:
                    continue
                col_std = df[var].std()
                tol = max(col_std * initial_tol_fraction * factor, 1e-6)
                mask &= (np.abs(df[var] - val) < tol)

            last_matched = df[mask]
            if len(last_matched) >= min_samples:
                return last_matched

        return last_matched


__all__ = ["SCMSolver"]
