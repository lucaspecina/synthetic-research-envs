"""EpisodeRunner: manages the step-by-step interaction loop."""

from __future__ import annotations

from sreg.models.episode import Action, ActionType, Episode, Observation, StepResult
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver


class EpisodeRunner:
    """Runs an episode step-by-step, processing agent actions.

    The runner maintains the episode state, validates actions,
    returns observations, and tracks budget usage.
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
            return self._handle_observe(action)
        elif action.type == ActionType.QUERY_DISTRIBUTION:
            return self._handle_query(action)
        elif action.type == ActionType.SUBMIT:
            return self._handle_submit(action)
        else:
            raise ValueError(f"Unknown action type: {action.type}")

    def _handle_observe(self, action: Action) -> StepResult:
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
