"""RL training integration with verifiers.

Adapter layer that wraps SREG as a verifiers-compatible environment
for RL training (GRPO) with tool-calling models.
"""

from sreg.training.dataset import generate_dataset, generate_src, src_to_rows
from sreg.training.types import EvalType, SubmitPayload

__all__ = [
    "EvalType",
    "SubmitPayload",
    "generate_dataset",
    "generate_src",
    "src_to_rows",
]
