"""WorldGenTool: generates worlds from template configurations."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from sreg.models.dag_spec import DAGSpec
from sreg.models.world import World
from sreg.world.templates.causal_chain import CausalChainTemplate
from sreg.world.templates.custom import CustomTemplate
from sreg.world.templates.fork_collider import ForkColliderTemplate
from sreg.world.templates.latent_preference import LatentPreferenceTemplate


class WorldGenConfig(BaseModel):
    """Configuration for world generation."""

    template_family: str = "latent_preference"
    num_nodes: int = Field(default=6, ge=3, le=20)
    num_latent: int = Field(default=1, ge=1)
    num_states: int = Field(default=3, ge=2, le=5)
    edge_strength: float = Field(default=0.7, ge=0.1, le=1.0)
    seed: int = Field(default=42)

    @model_validator(mode="after")
    def validate_node_counts(self) -> WorldGenConfig:
        if self.num_nodes < self.num_latent + 2:
            raise ValueError(
                f"num_nodes ({self.num_nodes}) must be >= num_latent + 2 "
                f"({self.num_latent + 2}): need at least 1 observable + 1 target"
            )
        return self


class CustomWorldGenConfig(BaseModel):
    """Configuration for custom world generation from a DAGSpec.

    Note: this is a transitional API, separate from WorldGenConfig.
    If it works well, it will be unified under a single generation API later.
    """

    dag_spec: DAGSpec
    edge_strength: float = Field(default=0.7, ge=0.1, le=1.0)
    seed: int = Field(default=42)
    edge_directions: dict[tuple[str, str], str] = Field(
        default_factory=dict,
        description=(
            "Edge direction hints: {(parent, child): 'positive'|'negative'}. "
            "Controls whether higher parent state leads to higher or lower child state."
        ),
    )


_TEMPLATES = {
    "latent_preference": LatentPreferenceTemplate(),
    "causal_chain": CausalChainTemplate(),
    "fork_collider": ForkColliderTemplate(),
}

_CUSTOM_TEMPLATE = CustomTemplate()


class WorldGenTool:
    """Generates worlds from structured configurations using registered templates."""

    def generate(self, config: WorldGenConfig) -> World:
        template = _TEMPLATES.get(config.template_family)
        if template is None:
            available = list(_TEMPLATES.keys())
            raise ValueError(f"Unknown template '{config.template_family}'. Available: {available}")
        return template.generate(
            seed=config.seed,
            num_nodes=config.num_nodes,
            num_latent=config.num_latent,
            num_states=config.num_states,
            edge_strength=config.edge_strength,
        )

    def generate_custom(self, config: CustomWorldGenConfig) -> World:
        """Generate a world from an arbitrary DAGSpec.

        This is a transitional method, separate from generate() to avoid
        breaking existing templates. If successful, both methods will be
        unified under a single API later.
        """
        return _CUSTOM_TEMPLATE.generate(
            dag_spec=config.dag_spec,
            edge_strength=config.edge_strength,
            seed=config.seed,
            edge_directions=config.edge_directions,
        )


__all__ = ["CustomWorldGenConfig", "WorldGenConfig", "WorldGenTool"]
