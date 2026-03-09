"""World generation templates."""

from sreg.world.templates.causal_chain import CausalChainTemplate
from sreg.world.templates.custom import CustomTemplate
from sreg.world.templates.fork_collider import ForkColliderTemplate
from sreg.world.templates.latent_preference import LatentPreferenceTemplate

__all__ = [
    "CausalChainTemplate",
    "CustomTemplate",
    "ForkColliderTemplate",
    "LatentPreferenceTemplate",
]
