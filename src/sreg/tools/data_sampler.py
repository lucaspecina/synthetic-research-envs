"""DataSampler: sample from a Bayesian network and present as realistic data assets."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sreg.models.research_problem import DataAsset
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver


class DataSamplerConfig(BaseModel):
    """Configuration for data sampling."""

    num_rows: int = Field(default=50, ge=1, le=10000)
    format: str = Field(
        default="tabular",
        description="'tabular', 'observations', or 'both'",
    )
    seed: int = Field(default=0)
    include_latent: bool = Field(
        default=False,
        description="Whether to include latent variables in the output (normally hidden)",
    )


class DataSampler:
    """Sample data from a world's Bayesian network and format as DataAssets."""

    def sample(self, world: World, config: DataSamplerConfig) -> list[DataAsset]:
        """Generate data assets by sampling from the world's joint distribution."""
        solver = ExactBayesSolver(world)
        assets: list[DataAsset] = []

        visible_nodes = [
            n for n in world.nodes
            if n.type != NodeType.LATENT or config.include_latent
        ]
        visible_names = [n.name for n in visible_nodes]

        if config.format in ("tabular", "both"):
            assets.append(self._tabular(world, solver, visible_names, config))

        if config.format in ("observations", "both"):
            assets.append(self._observations(world, solver, visible_names, config))

        return assets

    def _tabular(
        self,
        world: World,
        solver: ExactBayesSolver,
        visible_names: list[str],
        config: DataSamplerConfig,
    ) -> DataAsset:
        """Sample N rows as a tabular dataset."""
        rows: list[dict[str, str | float]] = []

        for i in range(config.num_rows):
            state = solver.sample_state(seed=config.seed + i)
            row: dict[str, str | float] = {"sample_id": i + 1}
            for name in visible_names:
                row[name] = state[name]
            rows.append(row)

        title = world.scenario_title or world.domain or "research"
        slug = title.lower().replace(" ", "_").replace("-", "_")[:40]
        return DataAsset(
            name=f"{slug}_data",
            description=(
                f"Dataset with {config.num_rows} samples. "
                f"Columns: {', '.join(visible_names)}."
            ),
            format="tabular",
            data=rows,
        )

    def _observations(
        self,
        world: World,
        solver: ExactBayesSolver,
        visible_names: list[str],
        config: DataSamplerConfig,
    ) -> DataAsset:
        """Sample a few observations as isolated datapoints."""
        observations: list[dict[str, str | float]] = []
        num_obs = min(5, config.num_rows)

        for i in range(num_obs):
            state = solver.sample_state(seed=config.seed + i)
            for name in visible_names:
                node = next(n for n in world.nodes if n.name == name)
                if node.type == NodeType.TARGET:
                    continue
                desc = node.description or name
                observations.append({
                    "observation": f"{desc}: {state[name]}",
                    "variable": name,
                    "value": state[name],
                    "sample": i + 1,
                })

        return DataAsset(
            name="field_observations",
            description=f"{len(observations)} individual field observations.",
            format="observations",
            data=observations,
        )


__all__ = ["DataSampler", "DataSamplerConfig"]
