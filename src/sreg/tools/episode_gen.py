"""EpisodeGenTool: generates episodes from worlds."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sreg.models.episode import Episode, Observation
from sreg.models.world import NodeType, World


class EpisodeGenConfig(BaseModel):
    """Configuration for episode generation."""

    budget: int = Field(default=5, gt=0, description="Number of observations the agent can make")
    node_cost: int = Field(default=1, ge=1, description="Default cost per observation")
    initial_evidence_count: int = Field(
        default=0, ge=0, description="Number of free initial observations"
    )
    seed: int = Field(default=0)


class EpisodeGenTool:
    """Generates episodes from a world and configuration."""

    def generate(
        self,
        world: World,
        config: EpisodeGenConfig,
        true_state: dict[str, str] | None = None,
    ) -> Episode:
        """Generate an episode from a world.

        Args:
            world: The world to generate an episode for.
            config: Episode configuration.
            true_state: If provided, used to generate initial evidence observations.
                        Otherwise initial_evidence is empty.
        """
        obs_nodes = [n for n in world.nodes if n.type == NodeType.OBSERVABLE]
        available = [n.name for n in obs_nodes]

        node_costs = {name: config.node_cost for name in available}

        initial_evidence: list[Observation] = []
        if true_state and config.initial_evidence_count > 0:
            import numpy as np

            rng = np.random.default_rng(config.seed)
            n_init = min(config.initial_evidence_count, len(available) - 1)
            init_nodes = rng.choice(available, size=n_init, replace=False).tolist()

            for node_name in init_nodes:
                state = true_state[node_name]
                initial_evidence.append(
                    Observation(
                        node=node_name,
                        state=state,
                        description=f"{node_name} was observed to be {state.upper()}",
                    )
                )
                available.remove(node_name)

        return Episode(
            id=f"ep-{world.id}-{config.seed:04d}",
            world_id=world.id,
            budget=config.budget,
            initial_evidence=initial_evidence,
            available_nodes=available,
            node_costs=node_costs,
            steps=[],
        )


__all__ = ["EpisodeGenConfig", "EpisodeGenTool"]
