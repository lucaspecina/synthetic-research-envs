"""SREG training module: verifiers-compatible RL environment.

Wraps the OI architecture (OIEpisodeRunner + scoring pipeline) as a
StatefulToolEnv for training with verifiers/GRPO.
"""

from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

from sreg.training.env import SregEnv  # noqa: E402

__all__ = ["SregEnv"]
