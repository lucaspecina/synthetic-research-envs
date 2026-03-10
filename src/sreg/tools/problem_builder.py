"""ProblemBuilder: package a World + data into a ResearchProblem for the agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

import networkx as nx

from sreg.models.research_problem import AvailableAction, ResearchActionType, ResearchProblem
from sreg.models.world import NodeType, World
from sreg.tools.data_sampler import DataSampler, DataSamplerConfig

if TYPE_CHECKING:
    from sreg.models.case_plan import CasePlan


class ProblemBuilder:
    """Build a ResearchProblem from a semantically enriched World."""

    def build(
        self,
        world: World,
        budget: int = 5,
        data_config: DataSamplerConfig | None = None,
        rich_data: bool = False,
        rich_actions: bool = False,
        case_plan: CasePlan | None = None,
    ) -> ResearchProblem:
        """Package a world into a research problem the agent can see.

        Args:
            world: A World with semantic fields populated.
            budget: How many observation actions the agent can take.
            data_config: Configuration for data sampling. Defaults to 50 tabular rows.
            rich_data: If True, use multi-dataset mode with missing data and
                narrative observations (overridden by explicit data_config).
            rich_actions: If True, generate actions with varied costs, types,
                and multi-node groupings based on DAG structure.
            case_plan: If provided, use the primary question's text as the
                visible research question instead of the generic template.
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
        if rich_actions:
            actions = self._build_rich_actions(world)
        else:
            actions = self._build_actions(world)

        # Find target
        target = next(n for n in world.nodes if n.type == NodeType.TARGET)

        # Build the research question
        question = self._build_question(world, target, case_plan)

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
        """Create semantic action descriptions from observable nodes (legacy mode)."""
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

    def _build_rich_actions(self, world: World) -> list[AvailableAction]:
        """Create rich actions with varied costs, types, and multi-node groupings.

        Strategy:
        - Nodes adjacent to target get cost 2 (specialized measurement)
        - Other individual nodes get cost 1 (basic measurement)
        - Sibling nodes (same parent) are grouped into a compound action
          with cost = number of nodes (no discount — the value is convenience)
        - At most 1 compound action to keep things manageable
        """
        # Build DAG for structure analysis
        dag = nx.DiGraph()
        for node in world.nodes:
            dag.add_node(node.name)
        for edge in world.edges:
            dag.add_edge(edge.from_node, edge.to_node)

        target_name = next(n.name for n in world.nodes if n.type == NodeType.TARGET)
        target_parents = set(dag.predecessors(target_name))
        obs_nodes = [n for n in world.nodes if n.type == NodeType.OBSERVABLE]
        obs_names = {n.name for n in obs_nodes}

        # Find sibling groups (observable nodes sharing a parent)
        parent_to_children: dict[str, list[str]] = {}
        for node_name in obs_names:
            for parent in dag.predecessors(node_name):
                children = [
                    c for c in dag.successors(parent)
                    if c in obs_names and c != target_name
                ]
                if len(children) >= 2:
                    key = parent
                    if key not in parent_to_children:
                        parent_to_children[key] = children

        # Pick the best sibling group for a compound action (largest group, max 3 nodes)
        compound_nodes: set[str] = set()
        if parent_to_children:
            best_parent = max(parent_to_children, key=lambda p: len(parent_to_children[p]))
            siblings = parent_to_children[best_parent][:3]
            if len(siblings) >= 2:
                compound_nodes = set(siblings)

        actions: list[AvailableAction] = []

        # Individual actions for non-compound nodes
        for node in obs_nodes:
            if node.name in compound_nodes:
                continue
            label = node.name.replace("_", " ")
            cost = 2 if node.name in target_parents else 1
            actions.append(
                AvailableAction(
                    action_type=ResearchActionType.OBSERVE,
                    node=node.name,
                    description=f"Measure {label}",
                    cost=cost,
                )
            )

        # Compound action for sibling group
        if compound_nodes:
            compound_list = sorted(compound_nodes)
            labels = [n.replace("_", " ") for n in compound_list]
            actions.append(
                AvailableAction(
                    action_type=ResearchActionType.OBSERVE,
                    nodes=compound_list,
                    description=f"Field survey: measure {', '.join(labels)}",
                    cost=len(compound_list),
                )
            )

        return actions

    def _build_question(
        self, world: World, target_node, case_plan: CasePlan | None = None,
    ) -> str:
        """Build the research question.

        If a CasePlan is provided, uses the primary question's text
        (what the LLM designed for this specific case). Otherwise falls
        back to a generic template.
        """
        states_str = ", ".join(target_node.states)

        # Use the plan's primary question if available
        if case_plan and case_plan.questions:
            primary = case_plan.questions[0]
            return (
                f"{primary.question_text}\n\n"
                f"Target variable: '{target_node.name}' "
                f"(possible states: {states_str}). "
                f"You may request additional measurements within your budget."
            )

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
