"""Reporting utilities for the eval/training harness.

Pure helpers for summarizing rollout outputs:
  - run_metadata: reproducibility context (git SHA, versions, timestamp)
  - summarize_values: mean + percentile distribution for a list of floats
  - per_case_breakdown: aggregate rollouts by problem_id
  - write_trajectories_jsonl: stream per-rollout details to JSONL

Separated from scripts/eval_oi.py so they can be unit-tested without
CLI glue, and so a future training script (scripts/train_sreg.py) can
reuse the same aggregation contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

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


# Fields to extract for trajectory dumps. Keeps the JSONL output tightly
# scoped: the expensive stuff (messages + tool calls) for qualitative
# review, the identity stuff (problem_id + example_id) to correlate with
# per-case breakdown, and the outcome stuff (reward + metrics + stop
# condition) so a reader can filter without reparsing.
_TRAJECTORY_FIELDS = (
    "problem_id",
    "example_id",
    "task",
    "reward",
    "is_completed",
    "is_truncated",
    "stop_condition",
    "metrics",
    "trajectory",
    "completion",
    "token_usage",
    "timing",
    "error",
)


def write_trajectories_jsonl(
    outputs: Sequence[dict], path: Path, *, fields: Sequence[str] | None = None,
) -> int:
    """Write one JSON line per rollout to `path`. Returns count written.

    Args:
        outputs: Sequence of RolloutOutput-like dicts.
        path: Output JSONL path. Parent dir created if missing.
        fields: Override the default fields written per rollout.

    Why JSONL and not a single JSON array: trajectory dumps can be tens
    of MB per rollout. JSONL lets a reader stream with `for line in f`
    instead of loading everything into memory, and a partial write (if
    the eval crashes mid-batch) still yields a parseable prefix.
    """
    fields = fields or _TRAJECTORY_FIELDS
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for o in outputs:
            record = {k: o.get(k) for k in fields}
            f.write(json.dumps(record, default=str) + "\n")
            count += 1
    return count


def _bootstrap_mean_ci(
    values: Sequence[float], *, n_resamples: int = 1000, alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap (1 - alpha) CI for the mean of `values`.

    Returns (lo, hi). Used for `mean_intra_group_std` because with small N
    (e.g. N=6 groups) the point estimate alone is misleading — operators
    need to see the uncertainty band before deciding H100 spend.
    """
    if not values:
        return (float("nan"), float("nan"))
    arr = np.asarray(list(values), dtype=float)
    rng = np.random.default_rng(seed)
    n = len(arr)
    means = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        means[i] = arr[idx].mean()
    lo = float(np.percentile(means, 100 * alpha / 2))
    hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
    return (lo, hi)


def variance_report(outputs: Sequence[dict]) -> dict:
    """Group-level variance diagnostics for GRPO signal audit (#39).

    GRPO normalizes advantages by intra-group std. If groups have near-zero
    variance (all rollouts identical), advantage=0 and no gradient flows.
    This helper surfaces whether the current env + policy + reward combo
    produces enough within-group spread to train on — BEFORE paying for
    H100 GPU-hours.

    Codex (2026-04-17) flagged two failure modes the naive "mean std"
    misses:
      1. "Submit/no-submit mixture" fakes variance: a group with 2 rollouts
         at +0.3 and 2 at -0.05 has std ~0.17 but the signal is only
         submit-vs-fail, not research quality. Report `submitted_only_*`
         to control for this.
      2. Small-N point estimates mislead. Bootstrap a 95% CI around
         `mean_intra_group_std` so the uncertainty is visible.

    Args:
        outputs: Sequence of RolloutOutput-like dicts with at least
            `problem_id`, `reward`. Uses `metrics.submitted` if present,
            falls back to `reward >= 0` as "submitted" heuristic.

    Returns:
        Dict with the aggregated diagnostics. `per_group` has the raw
        per-problem_id rewards for inspection of borderline cases.
    """
    if not outputs:
        return {
            "n_rollouts": 0,
            "n_groups": 0,
            "mean_reward": float("nan"),
            "mean_intra_group_std": float("nan"),
            "bootstrap_ci_95": [float("nan"), float("nan")],
            "submitted_only_mean_std": float("nan"),
            "submit_rate": float("nan"),
            "pct_zero_variance_groups": float("nan"),
            "pct_single_reward_groups": float("nan"),
            "mean_top1_top2_gap": float("nan"),
            "stop_condition_distribution": {},
            "step_count_reward_correlation": float("nan"),
            "per_group": {},
        }

    # Group by problem_id. "_unknown" catches state_columns hookup failures.
    groups: dict[str, list[dict]] = {}
    for o in outputs:
        pid = o.get("problem_id") or "_unknown"
        groups.setdefault(pid, []).append(dict(o))

    per_group: dict[str, dict] = {}
    intra_stds: list[float] = []
    submitted_stds: list[float] = []
    top_gaps: list[float] = []
    zero_var_count = 0
    single_reward_count = 0
    total_submitted = 0
    stop_conditions: dict[str, int] = {}
    all_step_counts: list[float] = []
    all_rewards_paired: list[float] = []

    for pid, group in groups.items():
        rewards = [float(g.get("reward", 0.0)) for g in group]
        metrics_list = [g.get("metrics") or {} for g in group]
        submitted_flags = [
            bool(m.get("submitted")) if "submitted" in m else (r >= 0)
            for m, r in zip(metrics_list, rewards)
        ]
        stop_list = [g.get("stop_condition") or "_unknown" for g in group]
        step_counts = [
            float(m.get("step_count", 0.0)) for m in metrics_list
        ]

        std = float(np.std(rewards, ddof=0)) if len(rewards) >= 2 else 0.0
        intra_stds.append(std)
        if std == 0.0:
            zero_var_count += 1
        if len(set(rewards)) <= 1:
            single_reward_count += 1

        # top1 - top2 gap: proxy for contrastive signal (more aligned with
        # GRPO advantage than raw std, per Codex). Undefined for groups
        # of size 1.
        if len(rewards) >= 2:
            sorted_r = sorted(rewards, reverse=True)
            top_gaps.append(sorted_r[0] - sorted_r[1])

        # Submitted-only std: descartes variance that is purely
        # submit/no-submit mixture. Requires >=2 submitted rollouts to
        # define.
        submitted_rewards = [r for r, s in zip(rewards, submitted_flags) if s]
        if len(submitted_rewards) >= 2:
            submitted_stds.append(float(np.std(submitted_rewards, ddof=0)))

        total_submitted += sum(submitted_flags)
        for sc in stop_list:
            stop_conditions[sc] = stop_conditions.get(sc, 0) + 1
        all_step_counts.extend(step_counts)
        all_rewards_paired.extend(rewards)

        per_group[pid] = {
            "n_rollouts": len(group),
            "rewards": rewards,
            "reward_mean": float(np.mean(rewards)),
            "reward_std": std,
            "n_unique_rewards": len(set(rewards)),
            "submitted_count": sum(submitted_flags),
            "submitted_only_std": (
                float(np.std(submitted_rewards, ddof=0))
                if len(submitted_rewards) >= 2 else None
            ),
            "stop_conditions": stop_list,
        }

    n_rollouts = len(outputs)
    n_groups = len(groups)

    # Pearson correlation step_count ↔ reward. Catches the "agent that
    # tries harder gets penalized" bug (negative correlation) — important
    # to surface before blaming the training loop for flat curves.
    if len(all_step_counts) >= 2 and np.std(all_step_counts) > 0:
        corr = float(np.corrcoef(all_step_counts, all_rewards_paired)[0, 1])
    else:
        corr = float("nan")

    mean_intra_std = float(np.mean(intra_stds)) if intra_stds else float("nan")
    ci_lo, ci_hi = _bootstrap_mean_ci(intra_stds) if intra_stds else (
        float("nan"), float("nan")
    )

    return {
        "n_rollouts": n_rollouts,
        "n_groups": n_groups,
        "mean_reward": float(np.mean(all_rewards_paired)),
        "mean_intra_group_std": mean_intra_std,
        "bootstrap_ci_95": [ci_lo, ci_hi],
        "submitted_only_mean_std": (
            float(np.mean(submitted_stds)) if submitted_stds else float("nan")
        ),
        "submitted_only_n_groups": len(submitted_stds),
        "submit_rate": total_submitted / n_rollouts if n_rollouts else 0.0,
        "pct_zero_variance_groups": (
            100.0 * zero_var_count / n_groups if n_groups else 0.0
        ),
        "pct_single_reward_groups": (
            100.0 * single_reward_count / n_groups if n_groups else 0.0
        ),
        "mean_top1_top2_gap": (
            float(np.mean(top_gaps)) if top_gaps else float("nan")
        ),
        "stop_condition_distribution": stop_conditions,
        "step_count_reward_correlation": corr,
        "per_group": per_group,
    }


# Gate thresholds — tuned from Codex consultation 2026-04-17. These are
# heuristics, not literature-cited cutoffs. Tweak as we learn.
_GATE_ALL_STD_MIN = 0.05
_GATE_SUBMITTED_STD_MIN = 0.03
_GATE_ZERO_VAR_MAX_PCT = 40.0


def variance_verdict(report: dict) -> dict:
    """Decide PASS / BORDERLINE / FAIL from a `variance_report()` output.

    Gates (all must pass for PASS):
      - `mean_intra_group_std >= 0.05` — baseline variance on all rewards
      - `submitted_only_mean_std >= 0.03` — variance among "successful"
        submissions, rules out signal that is purely submit/no-submit
        mixture
      - `pct_zero_variance_groups <= 40` — most groups need >=2 distinct
        rewards or GRPO collapses

    BORDERLINE if 2/3 gates pass (likely worth a second run at higher
    temperature). FAIL if 0 or 1 gate passes (needs intervention before
    spending H100 hours).

    Returns a dict with per-gate booleans, the computed verdict, and a
    human-readable `recommendation` string.
    """
    gates = {
        "all_std_ok": (
            not np.isnan(report["mean_intra_group_std"]) and
            report["mean_intra_group_std"] >= _GATE_ALL_STD_MIN
        ),
        "submitted_std_ok": (
            not np.isnan(report["submitted_only_mean_std"]) and
            report["submitted_only_mean_std"] >= _GATE_SUBMITTED_STD_MIN
        ),
        "not_too_many_collapsed": (
            report["pct_zero_variance_groups"] <= _GATE_ZERO_VAR_MAX_PCT
        ),
    }
    passed = sum(gates.values())
    if passed == 3:
        verdict = "PASS"
        rec = (
            "GRPO has signal. Proceed to H100 setup (#38) and first RL run (#24)."
        )
    elif passed == 2:
        verdict = "BORDERLINE"
        rec = (
            "Signal is ambiguous. Recommend a second audit run at higher "
            "temperature (e.g. 1.0) on the same prompts before committing "
            "to H100 spend."
        )
    else:
        verdict = "FAIL"
        rec = (
            "Insufficient signal for GRPO. Do NOT proceed to H100 yet — "
            "create intervention issues (reward shaping, temperature "
            "adjustment, penalty rebalancing) and re-audit."
        )
    return {
        "verdict": verdict,
        "gates": gates,
        "thresholds": {
            "all_std_min": _GATE_ALL_STD_MIN,
            "submitted_std_min": _GATE_SUBMITTED_STD_MIN,
            "zero_var_max_pct": _GATE_ZERO_VAR_MAX_PCT,
        },
        "recommendation": rec,
    }


__all__ = [
    "run_metadata",
    "summarize_values",
    "per_case_breakdown",
    "write_trajectories_jsonl",
    "variance_report",
    "variance_verdict",
]
