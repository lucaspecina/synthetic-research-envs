"""EpisodeRunner: manages the step-by-step interaction loop."""

from __future__ import annotations

import networkx as nx
import numpy as np

from sreg.models.episode import Action, ActionDef, ActionType, Episode, Observation, StepResult
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver


class EpisodeRunner:
    """Runs an episode step-by-step, processing agent actions.

    The runner maintains the episode state, validates actions,
    returns observations, and tracks budget usage.

    Supports two modes:
    - Legacy: uses ``available_nodes`` + ``node_costs`` (single-node observe)
    - Rich: uses ``action_defs`` for multi-node and typed actions

    Intervention semantics:
    - Intervene actions fix a node to a specific state (do-operation).
    - Tracked separately in ``_interventions`` (not ``_evidence``).
    - Post-intervention observations of descendant nodes are sampled
      from the interventional distribution P(Y | do(X=x), evidence).
    - A node cannot be both observed and intervened in the same episode.
    """

    def __init__(self, world: World, episode: Episode, true_state: dict[str, str]):
        self.world = world
        self.episode = episode
        self.true_state = true_state
        self._solver = ExactBayesSolver(world)
        self._evidence: dict[str, str] = {}
        self._interventions: dict[str, str] = {}
        self._step = 0
        self._sample_counter = 0  # monotonic counter for RNG seeding
        self._budget_remaining = episode.budget
        self._finished = False
        self._used_action_ids: set[str] = set()

        # Build action map from rich action definitions
        self._action_map: dict[str, ActionDef] = {
            ad.id: ad for ad in episode.action_defs
        }

        # Build DAG for descendant lookups
        self._dag = nx.DiGraph()
        for node in world.nodes:
            self._dag.add_node(node.name)
        for edge in world.edges:
            self._dag.add_edge(edge.from_node, edge.to_node)

        # Apply initial evidence
        for obs in episode.initial_evidence:
            self._evidence[obs.node] = obs.state

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def budget_remaining(self) -> int:
        return self._budget_remaining

    @property
    def evidence(self) -> dict[str, str]:
        return dict(self._evidence)

    @property
    def interventions(self) -> dict[str, str]:
        return dict(self._interventions)

    def step(self, action: Action) -> StepResult:
        """Process a single agent action and return the result."""
        if self._finished:
            raise RuntimeError("Episode is already finished")

        if action.type == ActionType.INTERVENE:
            if action.action_id and action.action_id in self._action_map:
                return self._handle_rich_action(action)
            raise ValueError("Intervene actions require an action_id with effects")

        if action.type == ActionType.OBSERVE:
            if action.action_id and action.action_id in self._action_map:
                return self._handle_rich_action(action)
            return self._handle_observe(action)
        elif action.type == ActionType.QUERY_DISTRIBUTION:
            return self._handle_query(action)
        elif action.type == ActionType.SUBMIT:
            return self._handle_submit(action)
        else:
            raise ValueError(f"Unknown action type: {action.type}")

    def _handle_observe(self, action: Action) -> StepResult:
        """Handle single-node observe (legacy mode)."""
        node_name = action.node
        if node_name not in self.episode.available_nodes:
            raise ValueError(f"Node '{node_name}' is not available for observation")
        if node_name in self._evidence:
            raise ValueError(f"Node '{node_name}' has already been observed")
        if node_name in self._interventions:
            raise ValueError(
                f"Node '{node_name}' was already intervened on "
                f"and cannot be observed in the same episode"
            )

        cost = self.episode.node_costs.get(node_name, 1)
        if cost > self._budget_remaining:
            raise ValueError(
                f"Insufficient budget: need {cost}, have {self._budget_remaining}"
            )

        state = self._get_node_value(node_name)
        self._evidence[node_name] = state
        self._budget_remaining -= cost

        observation = Observation(
            node=node_name,
            state=state,
            description=f"{node_name} was observed to be {state.upper()}",
        )

        result = StepResult(
            step=self._step,
            action=action,
            observation=observation,
            remaining_budget=self._budget_remaining,
        )
        self.episode.steps.append(result)
        self._step += 1
        return result

    def _handle_rich_action(self, action: Action) -> StepResult:
        """Handle rich actions (observe or intervene) via action_id."""
        action_def = self._action_map[action.action_id]

        # Validate action type consistency
        expected_type = "intervene" if action.type == ActionType.INTERVENE else "observe"
        if action_def.action_type != expected_type:
            raise ValueError(
                f"Action type mismatch: action '{action.action_id}' is defined as "
                f"'{action_def.action_type}' but was called with type '{action.type}'"
            )

        if action.action_id in self._used_action_ids:
            raise ValueError(f"Action '{action.action_id}' has already been used")

        if action_def.cost > self._budget_remaining:
            raise ValueError(
                f"Insufficient budget: action '{action.action_id}' costs "
                f"{action_def.cost}, have {self._budget_remaining}"
            )

        if action_def.action_type == "intervene":
            return self._execute_intervene(action, action_def)
        else:
            return self._execute_observe(action, action_def)

    def _execute_observe(self, action: Action, action_def: ActionDef) -> StepResult:
        """Execute an observe action: reveal node values from true_state."""
        # Check no nodes already observed or intervened
        for node_name in action_def.nodes:
            if node_name in self._evidence:
                raise ValueError(
                    f"Node '{node_name}' (from action '{action.action_id}') "
                    f"has already been observed"
                )
            if node_name in self._interventions:
                raise ValueError(
                    f"Node '{node_name}' was already intervened on "
                    f"and cannot be observed in the same episode"
                )

        # Reveal all nodes — use interventional sample if any interventions active
        observations: list[Observation] = []
        for node_name in action_def.nodes:
            state = self._get_node_value(node_name)
            self._evidence[node_name] = state
            observations.append(
                Observation(
                    node=node_name,
                    state=state,
                    description=f"{node_name} was observed to be {state.upper()}",
                )
            )

        self._budget_remaining -= action_def.cost
        self._used_action_ids.add(action.action_id)

        result = StepResult(
            step=self._step,
            action=action,
            observation=observations[0],
            extra_observations=observations[1:] if len(observations) > 1 else [],
            remaining_budget=self._budget_remaining,
        )
        self.episode.steps.append(result)
        self._step += 1
        return result

    def _execute_intervene(self, action: Action, action_def: ActionDef) -> StepResult:
        """Execute an intervene action: fix nodes to specified states (do-operation)."""
        if not action_def.effects:
            raise ValueError(
                f"Intervene action '{action.action_id}' has no effects defined"
            )

        # Validate nodes
        for node_name, state in action_def.effects.items():
            if node_name in self._interventions:
                raise ValueError(
                    f"Node '{node_name}' has already been intervened on"
                )
            if node_name in self._evidence:
                raise ValueError(
                    f"Node '{node_name}' was already observed "
                    f"and cannot be intervened on in the same episode"
                )
            # Validate state is valid for this node
            node_obj = next((n for n in self.world.nodes if n.name == node_name), None)
            if node_obj is None:
                raise ValueError(f"Node '{node_name}' does not exist in the world")
            if state not in node_obj.states:
                raise ValueError(
                    f"State '{state}' is not valid for node '{node_name}'. "
                    f"Valid states: {list(node_obj.states)}"
                )

        # Apply interventions
        observations: list[Observation] = []
        for node_name, state in action_def.effects.items():
            self._interventions[node_name] = state
            observations.append(
                Observation(
                    node=node_name,
                    state=state,
                    description=f"{node_name} was set to {state.upper()} (intervention)",
                )
            )

        # Invalidate cached true_state for descendants of intervened nodes
        self._invalidate_descendants(list(action_def.effects.keys()))

        self._budget_remaining -= action_def.cost
        self._used_action_ids.add(action.action_id)

        result = StepResult(
            step=self._step,
            action=action,
            observation=observations[0],
            extra_observations=observations[1:] if len(observations) > 1 else [],
            remaining_budget=self._budget_remaining,
        )
        self.episode.steps.append(result)
        self._step += 1
        return result

    def _get_node_value(self, node_name: str) -> str:
        """Get a node's value, respecting active interventions.

        If interventions are active and the node is a descendant of an
        intervened node, sample from the interventional distribution
        P(node | do(interventions), evidence) instead of using true_state.
        """
        if not self._interventions:
            return self.true_state[node_name]

        # If this node was directly intervened, return the intervention value
        if node_name in self._interventions:
            return self._interventions[node_name]

        # Check if node is a descendant of any intervened node
        is_descendant = any(
            nx.has_path(self._dag, iv_node, node_name)
            for iv_node in self._interventions
        )

        if not is_descendant:
            return self.true_state[node_name]

        # Node is downstream of intervention — sample from interventional distribution
        dist = self._solver.causal_query(
            node_name, do=self._interventions, evidence=self._evidence
        )
        states = list(dist.keys())
        probs = np.array(list(dist.values()))
        # Normalize to handle floating point
        probs = probs / probs.sum()
        rng = np.random.default_rng(self._sample_counter)
        self._sample_counter += 1
        chosen_idx = rng.choice(len(states), p=probs)
        return states[chosen_idx]

    def _invalidate_descendants(self, intervened_nodes: list[str]) -> None:
        """Mark descendants of intervened nodes so they get resampled.

        We don't resample eagerly — _get_node_value handles it lazily.
        But we do need to remove any already-observed descendants from
        evidence, since those observations are now stale.

        Note: for Slice B MVP we prohibit observe->intervene on the same
        node, so this mainly guards against future edge cases.

        Known limitation: if a descendant was observed via a rich action_id,
        that action_id stays in _used_action_ids even after evidence is
        invalidated. The agent cannot re-execute the same action. This is
        acceptable for MVP since observe/intervene conflict checks prevent
        the common case. See Codex review 2026-03-13.
        """
        for iv_node in intervened_nodes:
            for desc in nx.descendants(self._dag, iv_node):
                if desc in self._evidence:
                    del self._evidence[desc]

    def _handle_query(self, action: Action) -> StepResult:
        node_name = action.node
        if self._interventions:
            distribution = self._solver.causal_query(
                node_name, do=self._interventions, evidence=self._evidence
            )
        else:
            distribution = self._solver.posterior(node_name, self._evidence)

        result = StepResult(
            step=self._step,
            action=action,
            distribution=distribution,
            remaining_budget=self._budget_remaining,
        )
        self.episode.steps.append(result)
        self._step += 1
        return result

    def _handle_submit(self, action: Action) -> StepResult:
        self._finished = True

        result = StepResult(
            step=self._step,
            action=action,
            remaining_budget=self._budget_remaining,
        )
        self.episode.steps.append(result)
        self._step += 1
        return result

    def true_posterior(self, target: str) -> dict[str, float]:
        """Get the true posterior given current evidence and interventions."""
        if self._interventions:
            return self._solver.causal_query(
                target, do=self._interventions, evidence=self._evidence
            )
        return self._solver.posterior(target, self._evidence)


__all__ = ["EpisodeRunner"]
