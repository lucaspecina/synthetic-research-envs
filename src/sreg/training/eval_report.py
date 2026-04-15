"""Reporting utilities for the eval/training harness.

Pure helpers for summarizing rollout outputs:
  - run_metadata: reproducibility context (git SHA, versions, timestamp)
  - summarize_values: mean + percentile distribution for a list of floats
  - per_case_breakdown: aggregate rollouts by problem_id

Separated from scripts/eval_oi.py so they can be unit-tested without
CLI glue, and so a future training script (scripts/train_sreg.py) can
reuse the same aggregation contract.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np


def run_metadata(*, repo_root: Path | None = None) -> dict:
    """Reproducibility metadata: git SHA, library versions, timestamp.

    Args:
        repo_root: Path to the git repo root. Defaults to the project root
            inferred from this file's location. Exposed for tests that
            want to pin the command to a known directory.

    Captures the invocation context so two output JSONs can be diffed to
    explain why scores moved. Best-effort — git commands may fail in
    non-git environments; each field falls back to 'unknown' rather than
    crashing the eval.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]

    meta: dict[str, object] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
    }

    try:
        import verifiers as vf

        meta["verifiers_version"] = getattr(vf, "__version__", "unknown")
    except Exception:
        meta["verifiers_version"] = "unknown"

    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(repo_root),
        ).strip()
        meta["git_sha"] = sha
    except Exception:
        meta["git_sha"] = "unknown"

    # git_dirty = True if there are uncommitted changes. Useful when
    # diffing runs: a dirty-worktree run cannot be reproduced from the
    # SHA alone.
    try:
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(repo_root),
        )
        meta["git_dirty"] = bool(dirty.strip())
    except Exception:
        meta["git_dirty"] = None

    return meta


def summarize_values(values: Sequence[float]) -> dict:
    """Mean + percentiles for a list of floats. Empty list returns {}.

    Reports p50/p90/p95/max always; p99 only when N>=50. Smaller samples
    give a nonsense p99 that looks precise but is dominated by a single
    datapoint — better to omit than mislead.
    """
    if not values:
        return {}
    arr = np.asarray(list(values), dtype=float)
    result: dict[str, float | int] = {
        "n": int(len(values)),
        "mean": float(arr.mean()),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "p50": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
    }
    if len(values) >= 50:
        result["p99"] = float(np.percentile(arr, 99))
    return result


def per_case_breakdown(outputs: Sequence[dict]) -> dict:
    """Aggregate rollouts by problem_id — surfaces which cases are outliers.

    Returns {problem_id: {n_rollouts, reward_mean, reward_max, metrics_mean}}.
    A batch-wide mean can hide a single poisoned case dragging the
    average down; per-case breakdown is what lets operators spot that
    without dumping full trajectories.

    Rollouts with no problem_id are grouped under "_unknown" rather than
    silently dropped (otherwise we'd hide a real bug: the state_columns
    hookup failed and the column didn't come through).
    """
    groups: dict[str, list[dict]] = {}
    for o in outputs:
        pid = o.get("problem_id") or "_unknown"
        groups.setdefault(pid, []).append(dict(o))

    breakdown: dict[str, dict] = {}
    for pid, group in groups.items():
        rewards = [float(g.get("reward", 0.0)) for g in group]
        metrics_per_rollout = [g.get("metrics") or {} for g in group]

        all_keys: set[str] = set()
        for m in metrics_per_rollout:
            all_keys.update(m.keys())

        metric_means: dict[str, float] = {}
        for k in sorted(all_keys):
            vals = [m.get(k) for m in metrics_per_rollout if m.get(k) is not None]
            if vals:
                metric_means[k] = float(np.mean(vals))

        breakdown[pid] = {
            "n_rollouts": len(group),
            "reward_mean": float(np.mean(rewards)),
            "reward_max": float(np.max(rewards)),
            "metrics_mean": metric_means,
        }
    return breakdown


__all__ = ["run_metadata", "summarize_values", "per_case_breakdown"]
