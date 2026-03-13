"""RL training integration with verifiers.

Adapter layer that wraps SREG as a verifiers-compatible environment
for RL training (GRPO) with tool-calling models.
"""

from sreg.training.types import EvalType, SubmitPayload

__all__ = ["EvalType", "SubmitPayload"]
