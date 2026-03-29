"""Structural Causal Model (SCM) world engine.

Each variable is defined by a structural equation (function of parents + noise).
The causal graph supports d-separation, do-calculus, and identifiability checks.
Reward computation uses Monte Carlo sampling against the true SCM.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Callable

import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class VariableMeta:
    """Metadata for a variable in the SCM."""

    unit: str = ""
    range: tuple[float, float] = (0.0, 1.0)
    description: str = ""


EquationFn = Callable[[dict[str, float], np.random.Generator], float]
"""Signature: (parents_dict, rng) -> value.

For root nodes, parents_dict is empty.
rng is a numpy Generator for reproducible noise.
"""


@dataclass
class SCMWorld:
    """A world defined by a causal graph + structural equations.

    Each variable is computed as:
        X_i = f_i(parents(X_i), noise_i)

    where f_i is an arbitrary Python function. This generalizes BNs:
    - BN with CPD tables: f_i samples from a categorical given parent states
    - Linear Gaussian: f_i = intercept + sum(coef * parent) + gaussian_noise
    - Nonlinear SCM: f_i = any function (sigmoid, threshold, sqrt, etc.)

    The graph determines d-separation, identifiability, and adjustment sets.
    The equations determine the quantitative relationships.
    """

    graph: dict[str, list[str]]
    """Adjacency list: {child: [parent1, parent2, ...]}. Roots have empty lists."""

    equations: dict[str, EquationFn]
    """Structural equations: {variable: f(parents_dict, rng) -> value}."""

    variable_meta: dict[str, VariableMeta] = field(default_factory=dict)
    """Optional metadata (units, ranges, descriptions) for each variable."""

    id: str = ""
    """Unique identifier for this world (used in Task.world_id)."""

    latent_variables: set[str] = field(default_factory=set)
    """Variables that are not directly observable (hidden from the agent)."""

    _dag: nx.DiGraph = field(default=None, init=False, repr=False)
    _topo_order: list[str] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._build_dag()
        self._validate()

    def _build_dag(self) -> None:
        """Build networkx DAG from the adjacency list."""
        self._dag = nx.DiGraph()
        for child, parents in self.graph.items():
            self._dag.add_node(child)
            for parent in parents:
                self._dag.add_edge(parent, child)
        try:
            self._topo_order = list(nx.topological_sort(self._dag))
        except nx.NetworkXUnfeasible:
            raise ValueError("Graph contains cycles")

    def _validate(self) -> None:
        """Validate that the SCM is well-formed."""
        if not nx.is_directed_acyclic_graph(self._dag):
            raise ValueError("Graph contains cycles")

        graph_vars = set(self.graph.keys())
        eq_vars = set(self.equations.keys())

        # Every variable in the graph must have an equation
        missing_eq = graph_vars - eq_vars
        if missing_eq:
            raise ValueError(f"Variables without equations: {missing_eq}")

        # Every parent referenced must exist as a variable
        all_parents = set()
        for parents in self.graph.values():
            all_parents.update(parents)
        unknown_parents = all_parents - graph_vars
        if unknown_parents:
            raise ValueError(f"Parents reference unknown variables: {unknown_parents}")

        # Latent variables must be actual variables
        unknown_latent = self.latent_variables - graph_vars
        if unknown_latent:
            raise ValueError(f"Latent variables not in graph: {unknown_latent}")

    @property
    def dag(self) -> nx.DiGraph:
        """The underlying directed acyclic graph."""
        return self._dag

    @property
    def variables(self) -> list[str]:
        """All variables in topological order."""
        return list(self._topo_order)

    @property
    def roots(self) -> list[str]:
        """Variables with no parents."""
        return [v for v in self._topo_order if not self.graph[v]]

    def parents(self, variable: str) -> list[str]:
        """Parents of a variable."""
        return list(self.graph[variable])

    def children(self, variable: str) -> list[str]:
        """Children of a variable."""
        return [v for v, parents in self.graph.items() if variable in parents]

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def _sample_one(
        self,
        rng: np.random.Generator,
        do: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Sample a single observation from the SCM.

        Args:
            rng: Numpy random generator.
            do: Interventions {variable: fixed_value}. When set, the variable's
                equation is replaced with the constant (edges from parents cut).
        """
        do = do or {}
        state: dict[str, float] = {}

        for var in self._topo_order:
            if var in do:
                # Intervention: fix value, ignore parents
                state[var] = do[var]
            else:
                parents_dict = {p: state[p] for p in self.graph[var]}
                state[var] = self.equations[var](parents_dict, rng)

        return state

    def sample(
        self,
        n: int = 1000,
        seed: int | None = None,
        do: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Generate n samples from the SCM (observational or interventional).

        Args:
            n: Number of samples.
            seed: Random seed for reproducibility.
            do: Interventions. If provided, the specified variables are fixed
                and their parent edges are cut (Pearl's do-operator).

        Returns:
            DataFrame with one column per variable, n rows.
        """
        rng = np.random.default_rng(seed)
        rows = [self._sample_one(rng, do=do) for _ in range(n)]
        return pd.DataFrame(rows, columns=self.variables)

    def interventional_distribution(
        self,
        target: str,
        do: dict[str, float],
        n: int = 100_000,
        seed: int | None = None,
    ) -> np.ndarray:
        """Compute P(target | do(interventions)) via Monte Carlo.

        Args:
            target: Variable to get the distribution of.
            do: Interventions {variable: value}.
            n: Number of Monte Carlo samples.
            seed: Random seed.

        Returns:
            1D array of n samples of the target variable under intervention.
        """
        df = self.sample(n=n, seed=seed, do=do)
        return df[target].values

    def observational_distribution(
        self,
        target: str,
        n: int = 100_000,
        seed: int | None = None,
    ) -> np.ndarray:
        """Compute P(target) via Monte Carlo (no intervention).

        Args:
            target: Variable to get the distribution of.
            n: Number of Monte Carlo samples.
            seed: Random seed.

        Returns:
            1D array of n samples of the target variable.
        """
        df = self.sample(n=n, seed=seed)
        return df[target].values

    # ------------------------------------------------------------------
    # Graph queries (these depend ONLY on the DAG, not the equations)
    # ------------------------------------------------------------------

    def is_d_separated(
        self,
        x: str | set[str],
        y: str | set[str],
        z: set[str] | None = None,
    ) -> bool:
        """Test d-separation: X _||_ Y | Z in the DAG."""
        x_set = {x} if isinstance(x, str) else x
        y_set = {y} if isinstance(y, str) else y
        z_set = z or set()
        return nx.is_d_separator(self._dag, x_set, y_set, z_set)

    @property
    def observable_variables(self) -> list[str]:
        """Variables that are directly observable (not latent)."""
        return [v for v in self._topo_order if v not in self.latent_variables]

    def get_all_backdoor_adjustment_sets(
        self, treatment: str, outcome: str
    ) -> list[frozenset[str]]:
        """Find all minimal backdoor adjustment sets for treatment -> outcome.

        A set Z satisfies the backdoor criterion if:
        1. No node in Z is a descendant of treatment.
        2. Z d-separates treatment and outcome in the graph with outgoing
           edges of treatment removed.

        Returns:
            List of frozensets. Each is a minimal valid adjustment set.
            Empty list means the effect is not identifiable via backdoor.
            A frozenset() in the list means no adjustment is needed.
        """
        descendants_of_x = nx.descendants(self._dag, treatment)
        candidates = sorted(
            set(self._dag.nodes) - descendants_of_x - {treatment, outcome}
        )

        # Manipulated graph: remove outgoing edges of treatment
        manipulated = self._dag.copy()
        outgoing = list(manipulated.out_edges(treatment))
        manipulated.remove_edges_from(outgoing)

        # Guard against large candidate sets — falls back to single heuristic
        # set instead of exhaustive enumeration. Log so callers are aware.
        if len(candidates) > 15:
            logger.warning(
                "get_all_backdoor_adjustment_sets: %d candidates for "
                "(%s -> %s), falling back to single heuristic set.",
                len(candidates), treatment, outcome,
            )
            result = self.adjustment_set(treatment, outcome)
            if result is not None:
                return [frozenset(result)]
            return []

        # Enumerate all valid sets from smallest to largest
        valid: list[frozenset[str]] = []
        for r in range(len(candidates) + 1):
            for subset in itertools.combinations(candidates, r):
                z = frozenset(subset)
                if nx.is_d_separator(manipulated, {treatment}, {outcome}, z):
                    valid.append(z)

        if not valid:
            return []

        # Keep only minimal sets (no proper subset already in the list)
        minimal: list[frozenset[str]] = []
        for s in sorted(valid, key=len):
            if not any(m < s for m in minimal):
                minimal.append(s)

        return minimal

    def adjustment_set(self, treatment: str, outcome: str) -> set[str] | None:
        """Find a valid adjustment set for the causal effect of treatment on outcome.

        Uses the backdoor criterion: a set Z satisfies the backdoor criterion
        relative to (X, Y) if:
        1. No node in Z is a descendant of X
        2. Z blocks every path between X and Y that contains an arrow into X

        Returns None if no valid adjustment set exists (e.g., unidentifiable).
        Returns an empty set if no adjustment is needed.
        """
        # Simple approach: non-descendants of treatment, excluding treatment and outcome
        descendants_of_x = nx.descendants(self._dag, treatment)
        candidates = set(self._dag.nodes) - descendants_of_x - {treatment, outcome}

        # Check if candidates block all backdoor paths
        # A backdoor path is a path from treatment to outcome that starts with
        # an arrow INTO treatment. We check if conditioning on candidates
        # d-separates treatment from outcome in the manipulated graph
        # (graph with outgoing edges of treatment removed).
        manipulated = self._dag.copy()
        outgoing = list(manipulated.out_edges(treatment))
        manipulated.remove_edges_from(outgoing)

        if nx.is_d_separator(manipulated, {treatment}, {outcome}, candidates):
            # Try to find a minimal subset
            minimal = set()
            for node in candidates:
                # Check if removing this node from the set breaks d-separation
                test_set = (candidates - {node}) | minimal
                if not nx.is_d_separator(manipulated, {treatment}, {outcome}, test_set):
                    minimal.add(node)

            # Verify the minimal set works
            if nx.is_d_separator(manipulated, {treatment}, {outcome}, minimal):
                return minimal
            return candidates

        return None


# ------------------------------------------------------------------
# Scoring utilities for continuous distributions
# ------------------------------------------------------------------


def kl_divergence_histogram(
    p_samples: np.ndarray,
    q_samples: np.ndarray,
    bins: int = 50,
    epsilon: float = 1e-10,
) -> float:
    """KL(P || Q) estimated via histogram binning.

    Args:
        p_samples: Samples from the "true" distribution P.
        q_samples: Samples from the "approximate" distribution Q.
        bins: Number of histogram bins.
        epsilon: Small constant to avoid log(0).

    Returns:
        KL divergence in nats. Lower = better match.
    """
    # Use shared bin edges covering both distributions
    all_samples = np.concatenate([p_samples, q_samples])
    bin_edges = np.linspace(all_samples.min(), all_samples.max(), bins + 1)

    p_hist, _ = np.histogram(p_samples, bins=bin_edges, density=True)
    q_hist, _ = np.histogram(q_samples, bins=bin_edges, density=True)

    # Normalize to proper probability distributions
    bin_width = bin_edges[1] - bin_edges[0]
    p_probs = p_hist * bin_width + epsilon
    q_probs = q_hist * bin_width + epsilon
    p_probs = p_probs / p_probs.sum()
    q_probs = q_probs / q_probs.sum()

    return float(np.sum(p_probs * np.log(p_probs / q_probs)))


def wasserstein_distance(p_samples: np.ndarray, q_samples: np.ndarray) -> float:
    """Earth Mover's Distance between two empirical distributions.

    Uses scipy's implementation. More robust than KL for distributions
    with different supports.
    """
    from scipy.stats import wasserstein_distance as _wd

    return float(_wd(p_samples, q_samples))


def kl_divergence_gaussian(
    mu1: float, var1: float, mu2: float, var2: float
) -> float:
    """Closed-form KL(N(mu1,var1) || N(mu2,var2)).

    Useful for Linear Gaussian SCMs where the interventional distribution
    is known to be Gaussian.
    """
    return 0.5 * (np.log(var2 / var1) + var1 / var2 + (mu1 - mu2) ** 2 / var2 - 1)


__all__ = [
    "EquationFn",
    "SCMWorld",
    "VariableMeta",
    "kl_divergence_gaussian",
    "kl_divergence_histogram",
    "wasserstein_distance",
]
