"""Exact Bayesian teacher solver using pgmpy VariableElimination."""

from __future__ import annotations

import networkx as nx
import numpy as np
from pgmpy.inference import VariableElimination

from sreg.models.episode import Action, ActionType
from sreg.models.teacher import TeacherOutput
from sreg.models.world import World
from sreg.world.pgmpy_utils import world_to_pgmpy


class ExactBayesSolver:
    """Exact Bayesian inference engine that plays episodes optimally.

    Maintains exact posteriors, computes information gain for every
    possible observation, and selects the action that maximizes
    entropy reduction on the target variable.
    """

    def __init__(self, world: World):
        self.world = world
        self._model = world_to_pgmpy(world)
        self._inference = VariableElimination(self._model)
        self._node_states = {n.name: n.states for n in world.nodes}
        self._cpd_map = {cpd.node: cpd for cpd in world.cpds}

    def posterior(self, target: str, evidence: dict[str, str] | None = None) -> dict[str, float]:
        """Compute P(target | evidence)."""
        result = self._inference.query([target], evidence=evidence or {})
        values = result.values.flatten().tolist()
        states = self._node_states[target]
        return dict(zip(states, values))

    def entropy(self, distribution: dict[str, float]) -> float:
        """Shannon entropy in bits."""
        probs = np.array(list(distribution.values()))
        probs = probs[probs > 0]
        return float(-np.sum(probs * np.log2(probs)))

    def information_gain(self, target: str, evidence: dict[str, str], candidate: str) -> float:
        """Expected information gain from observing candidate node.

        IG = H(target | evidence) - E_x[ H(target | evidence, candidate=x) ]
        """
        current_post = self.posterior(target, evidence)
        current_h = self.entropy(current_post)

        # P(candidate | evidence)
        candidate_dist = self.posterior(candidate, evidence)
        candidate_states = self._node_states[candidate]

        expected_h = 0.0
        for state in candidate_states:
            prob = candidate_dist[state]
            if prob < 1e-10:
                continue
            new_evidence = {**evidence, candidate: state}
            new_post = self.posterior(target, new_evidence)
            expected_h += prob * self.entropy(new_post)

        return max(0.0, current_h - expected_h)

    def optimal_action(
        self, target: str, evidence: dict[str, str], available: list[str]
    ) -> TeacherOutput:
        """Select the observation that maximizes information gain on the target."""
        current_post = self.posterior(target, evidence)
        current_h = self.entropy(current_post)

        if not available or current_h < 1e-6:
            return TeacherOutput(
                posterior=current_post,
                recommended_action=None,
                information_gain=0.0,
                entropy=current_h,
            )

        best_gain = -1.0
        best_node = None

        for node in available:
            gain = self.information_gain(target, evidence, node)
            if gain > best_gain:
                best_gain = gain
                best_node = node

        return TeacherOutput(
            posterior=current_post,
            recommended_action=Action(type=ActionType.OBSERVE, node=best_node),
            information_gain=max(0.0, best_gain),
            entropy=current_h,
        )

    def sample_state(self, seed: int | None = None) -> dict[str, str]:
        """Sample a complete world state from the joint distribution.

        Uses ancestral sampling: process nodes in topological order,
        sampling each from its conditional distribution given parent values.
        """
        rng = np.random.default_rng(seed)

        dag = nx.DiGraph()
        for node in self.world.nodes:
            dag.add_node(node.name)
        for edge in self.world.edges:
            dag.add_edge(edge.from_node, edge.to_node)

        order = list(nx.topological_sort(dag))
        state: dict[str, str] = {}

        for node_name in order:
            cpd = self._cpd_map[node_name]
            states = cpd.state_names[node_name]

            if not cpd.parents:
                probs = [row[0] for row in cpd.table]
            else:
                col_idx = self._col_index(cpd, state)
                probs = [row[col_idx] for row in cpd.table]

            chosen = rng.choice(len(states), p=probs)
            state[node_name] = states[chosen]

        return state

    def generate_trajectory(
        self,
        target: str,
        available: list[str],
        budget: int,
        seed: int | None = None,
    ) -> tuple[dict[str, str], list[TeacherOutput]]:
        """Generate an optimal trajectory for a sampled world state.

        Returns:
            (true_state, trajectory) where true_state is the full sampled
            assignment and trajectory is the sequence of TeacherOutputs.
        """
        true_state = self.sample_state(seed)

        evidence: dict[str, str] = {}
        remaining = list(available)
        trajectory: list[TeacherOutput] = []

        for _ in range(budget):
            if not remaining:
                break

            output = self.optimal_action(target, evidence, remaining)
            trajectory.append(output)

            if output.recommended_action is None:
                break

            node = output.recommended_action.node
            evidence[node] = true_state[node]
            remaining.remove(node)

        # Final posterior after all observations
        final_post = self.posterior(target, evidence)
        final_h = self.entropy(final_post)
        trajectory.append(
            TeacherOutput(
                posterior=final_post,
                recommended_action=None,
                information_gain=0.0,
                entropy=final_h,
            )
        )

        return true_state, trajectory

    def _col_index(self, cpd, state: dict[str, str]) -> int:
        """Compute CPD column index for a given parent state assignment.

        Column ordering matches pgmpy: first parent varies slowest.
        """
        col_idx = 0
        multiplier = 1
        for parent in reversed(cpd.parents):
            parent_states = cpd.state_names[parent]
            parent_idx = parent_states.index(state[parent])
            col_idx += parent_idx * multiplier
            multiplier *= len(parent_states)
        return col_idx


__all__ = ["ExactBayesSolver"]
