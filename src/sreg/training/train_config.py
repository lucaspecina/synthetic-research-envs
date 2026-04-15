"""YAML config loader + validator for train_sreg.py.

Separated from scripts/train_sreg.py so the risky parts (env var
expansion, path existence checks, train/holdout overlap detection) are
unit-testable without the full CLI / env / env-var setup.

Contract:
    cfg = load_config(Path("configs/smoke_rl.yaml"))
    validate_config(cfg)      # raises ValueError on any problem
    # cfg is a plain dict with the structure documented in
    # configs/smoke_rl.yaml. Kept as dict (not a dataclass) so
    # adding new keys doesn't require churning types everywhere.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


# Required fields and their expected types. Nested as tuple paths so the
# same table drives both the validation loop and error messages.
_REQUIRED: dict[tuple[str, ...], type | tuple[type, ...]] = {
    ("dataset", "dir"): str,
    ("dataset", "train_cases"): list,
    ("dataset", "holdout_cases"): list,
    ("rollout", "temperature"): (int, float),
    ("rollout", "max_turns"): int,
    ("rollout", "claim_cap"): int,
    ("rollout", "n_mc"): int,
    ("training", "rollouts_per_example"): int,
    ("training", "max_concurrent"): int,
    ("training", "total_steps"): int,
    ("training", "seed"): int,
}


def load_config(path: Path) -> dict:
    """Load a YAML config with shell-style env var expansion.

    ${VAR} and $VAR are expanded against os.environ before the YAML
    parser sees the text. This lets the config reference paths like
    `${SREG_P05_BATCH}` without hardcoding absolute filesystem paths —
    the same file then works on Windows dev and on H100 Linux.

    Unresolved env vars are left as the literal $VAR in the parsed
    config, which downstream validation will catch as a non-existent
    path instead of silently pointing at the wrong place.
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    expanded = os.path.expandvars(raw)
    cfg = yaml.safe_load(expanded)
    if cfg is None:
        raise ValueError(f"config is empty: {path}")
    if not isinstance(cfg, dict):
        raise ValueError(f"config must be a mapping at the top level: {path}")
    return cfg


def _get(cfg: dict, path: tuple[str, ...]) -> Any:
    """Walk a nested dict by key path. Raises KeyError with a path hint."""
    cur: Any = cfg
    for i, k in enumerate(path):
        if not isinstance(cur, dict) or k not in cur:
            missing = ".".join(path[: i + 1])
            raise KeyError(f"config missing key: {missing}")
        cur = cur[k]
    return cur


def validate_config(cfg: dict) -> None:
    """Check required fields, types, dataset dir existence, case layout.

    Fails fast with a single clear error per violation — the first
    problem to surface is the one the operator needs to fix. No
    "return list of errors" style because the downstream ones are
    usually cascading from the first.
    """
    # 1. Required fields + types
    for field_path, expected in _REQUIRED.items():
        try:
            val = _get(cfg, field_path)
        except KeyError as e:
            raise ValueError(str(e)) from None
        if not isinstance(val, expected):
            exp_name = (
                expected.__name__
                if isinstance(expected, type)
                else "/".join(t.__name__ for t in expected)
            )
            raise TypeError(
                f"config {'.'.join(field_path)}: expected {exp_name}, "
                f"got {type(val).__name__}"
            )

    # 2. Dataset dir must exist and resolve (catches unexpanded env vars).
    ds_dir = Path(cfg["dataset"]["dir"])
    if "$" in str(ds_dir):
        raise ValueError(
            f"dataset.dir looks like an unexpanded env var: {ds_dir}. "
            f"Set the referenced variable in the environment before running."
        )
    if not ds_dir.is_dir():
        raise ValueError(
            f"dataset.dir does not exist or is not a directory: {ds_dir}"
        )

    # 3. train_cases and holdout_cases must be disjoint (can't train on
    #    the holdout — that's the whole point of holding out).
    train = list(cfg["dataset"]["train_cases"])
    holdout = list(cfg["dataset"]["holdout_cases"])
    if not train:
        raise ValueError("dataset.train_cases is empty")
    overlap = set(train) & set(holdout)
    if overlap:
        raise ValueError(
            f"dataset.train_cases and holdout_cases overlap: {sorted(overlap)}"
        )
    # Duplicates within a list would make rollout counts ambiguous.
    for label, cases in (("train_cases", train), ("holdout_cases", holdout)):
        if len(cases) != len(set(cases)):
            dup = [c for c in set(cases) if cases.count(c) > 1]
            raise ValueError(f"dataset.{label} has duplicates: {sorted(dup)}")

    # 4. Every named case must have <dir>/<case>/src.json. A typo here
    #    would otherwise surface as a silent "loaded 9/10" at runtime —
    #    catch it at config time.
    missing = [
        case
        for case in sorted(set(train) | set(holdout))
        if not (ds_dir / case / "src.json").exists()
    ]
    if missing:
        raise ValueError(
            f"cases missing src.json under {ds_dir}: {missing}"
        )

    # 5. Sane numeric ranges — catches obvious typos (negative steps,
    #    zero rollouts) before they waste compute.
    if cfg["rollout"]["max_turns"] < 1:
        raise ValueError("rollout.max_turns must be >= 1")
    if cfg["rollout"]["claim_cap"] < 1:
        raise ValueError("rollout.claim_cap must be >= 1")
    if cfg["rollout"]["n_mc"] < 1:
        raise ValueError("rollout.n_mc must be >= 1")
    if not 0.0 <= cfg["rollout"]["temperature"] <= 2.0:
        raise ValueError(
            f"rollout.temperature out of [0, 2]: "
            f"{cfg['rollout']['temperature']}"
        )
    if cfg["training"]["rollouts_per_example"] < 1:
        raise ValueError("training.rollouts_per_example must be >= 1")
    if cfg["training"]["max_concurrent"] < 1:
        raise ValueError("training.max_concurrent must be >= 1")
    if cfg["training"]["total_steps"] < 1:
        raise ValueError("training.total_steps must be >= 1")


__all__ = ["load_config", "validate_config"]
