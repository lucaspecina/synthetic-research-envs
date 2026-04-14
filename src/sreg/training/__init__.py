"""SREG training module: verifiers-compatible RL environment.

Wraps the OI architecture (OIEpisodeRunner + scoring pipeline) as a
StatefulToolEnv for training with verifiers/GRPO.
"""

from sreg.training._compat import patch_fcntl_if_windows

patch_fcntl_if_windows()

from sreg.training.dataset import (  # noqa: E402
    PROMPT_VERSION,
    build_dataset,
    load_from_dir,
    load_srcs,
    load_srcs_from_paths,
    split_train_eval,
)
from sreg.training.env import SregEnv  # noqa: E402

__all__ = [
    "PROMPT_VERSION",
    "SregEnv",
    "build_dataset",
    "load_from_dir",
    "load_srcs",
    "load_srcs_from_paths",
    "split_train_eval",
]
