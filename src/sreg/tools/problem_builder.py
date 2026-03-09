"""ProblemBuilder: package a World + data into a ResearchProblem for the agent."""

from __future__ import annotations

from sreg.models.research_problem import AvailableAction, ResearchProblem
from sreg.models.world import NodeType, World
from sreg.tools.data_sampler import DataSampler, DataSamplerConfig


class ProblemBuilder:
    """Build a ResearchProblem from a semantically enriched World."""

    def build(
        self,
        world: World,
        budget: int = 5,
        data_config: DataSamplerConfig | None = None,
        rich_data: bool = False,
    ) -> ResearchProblem:
        """Package a world into a research problem the agent can see.

        Args:
            world: A World with semantic fields populated.
            budget: How many observation actions the agent can take.
            data_config: Configuration for data sampling. Defaults to 50 tabular rows.
            rich_data: If True, use multi-dataset mode with missing data and
                narrative observations (overridden by explicit data_config).
        """
        if data_config is None:
            if rich_data:
                data_config = DataSamplerConfig(
                    num_rows=50,
                    format="tabular",
                    seed=world.seed,
                    multi_dataset=True,
                    missing_rate=0.1,
                    narrative_observations=3,
                )
            else:
                data_config = DataSamplerConfig(
                    num_rows=50, format="tabular", seed=world.seed,
                )

        # Sample data
        sampler = DataSampler()
        data_assets = sampler.sample(world, data_config)

        # Build available actions from observable nodes
        actions = self._build_actions(world)

        # Find target
        target = next(n for n in world.nodes if n.type == NodeType.TARGET)

        # Build the research question
        question = self._build_question(world, target)

        return ResearchProblem(
            world_id=world.id,
            title=world.scenario_title or f"Research problem: {world.id}",
            description=world.scenario_description or world.description,
            domain=world.domain or "general",
            theoretical_context=world.theoretical_context,
            data_assets=data_assets,
            available_actions=actions,
            budget=budget,
            research_question=question,
            target_node=target.name,
            target_states=list(target.states),
        )

    def _build_actions(self, world: World) -> list[AvailableAction]:
        """Create semantic action descriptions from observable nodes."""
        actions: list[AvailableAction] = []
        for node in world.nodes:
            if node.type != NodeType.OBSERVABLE:
                continue
            label = node.name.replace("_", " ")
            actions.append(
                AvailableAction(
                    node=node.name,
                    description=f"Measure {label}",
                    cost=1,
                )
            )
        return actions

    def _build_question(self, world: World, target_node) -> str:
        """Build the research question from the world's semantic content."""
        states_str = ", ".join(target_node.states)
        if world.scenario_title:
            return (
                f"Based on the available data and your analysis, estimate the "
                f"probability distribution over '{target_node.name}' "
                f"(possible states: {states_str}). "
                f"You may request additional measurements within your budget."
            )
        return (
            f"Estimate the probability distribution over '{target_node.name}' "
            f"(possible states: {states_str}). "
            f"You have a budget of observations to refine your estimate."
        )


__all__ = ["ProblemBuilder"]
