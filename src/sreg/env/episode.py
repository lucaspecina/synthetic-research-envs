"""EpisodeRunner: manages the step-by-step interaction loop."""

from __future__ import annotations

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
    """

    def __init__(self, world: World, episode: Episode, true_state: dict[str, str]):
        self.world = world
        self.episode = episode
        self.true_state = true_state
        self._solver = ExactBayesSolver(world)
        self._evidence: dict[str, str] = {}
        self._step = 0
        self._budget_remaining = episode.budget
        self._finished = False
        self._used_action_ids: set[str] = set()

        # Build action map from rich action definitions
        self._action_map: dict[str, ActionDef] = {
            ad.id: ad for ad in episode.action_defs
        }

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

    def step(self, action: Action) -> StepResult:
        """Process a single agent action and return the result."""
        if self._finished:
            raise RuntimeError("Episode is already finished")

        if action.type == ActionType.OBSERVE:
            if action.action_id and action.action_id in self._action_map:
                return self._handle_compound_observe(action)
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

        cost = self.episode.node_costs.get(node_name, 1)
        if cost > self._budget_remaining:
            raise ValueError(
                f"Insufficient budget: need {cost}, have {self._budget_remaining}"
            )

        state = self.true_state[node_name]
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

    def _handle_compound_observe(self, action: Action) -> StepResult:
        """Handle multi-node observe via action_id (rich mode)."""
        action_def = self._action_map[action.action_id]

        if action.action_id in self._used_action_ids:
            raise ValueError(f"Action '{action.action_id}' has already been used")

        # Check no nodes already observed
        for node_name in action_def.nodes:
            if node_name in self._evidence:
                raise ValueError(
                    f"Node '{node_name}' (from action '{action.action_id}') "
                    f"has already been observed"
                )

        if action_def.cost > self._budget_remaining:
            raise ValueError(
                f"Insufficient budget: action '{action.action_id}' costs "
                f"{action_def.cost}, have {self._budget_remaining}"
            )

        # Reveal all nodes in this action
        observations: list[Observation] = []
        for node_name in action_def.nodes:
            state = self.true_state[node_name]
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

        # Return first observation in StepResult (compound results in extra_observations)
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

    def _handle_query(self, action: Action) -> StepResult:
        node_name = action.node
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
        """Get the true posterior given current evidence."""
        return self._solver.posterior(target, self._evidence)


__all__ = ["EpisodeRunner"]
