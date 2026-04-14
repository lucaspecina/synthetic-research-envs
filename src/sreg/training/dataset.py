"""HF Dataset loader for SregEnv training.

Converts a directory of frozen SRCs into a verifiers-compatible
Dataset with pre-rendered prompts and serialized info blobs.

Design (aligned with Codex review):
  - Render prompts at load time (cheaper, reproducible, frozen scaffold)
  - Embed full src_json in info (self-contained, no filesystem dep at rollout)
  - Validate by actually running: SRC must load SQs, reconstruct world, etc.
  - Explicit-by-id train/eval split (random too noisy at n<50)

Usage:
    from sreg.training.dataset import load_from_dir

    ds = load_from_dir(Path("results/v1_canonical_batch"))
    # or with eval split:
    train, eval_ds = load_from_dir(
        Path("results/v1_canonical_batch"),
        eval_ids=["poverty_reduction_china", "vaca_muerta"],
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from datasets import Dataset

logger = logging.getLogger(__name__)

# Prompt template version. Bump when OI prompt builders change so older
# serialized datasets are invalidated instead of silently drifting.
PROMPT_VERSION = "v1"


def _hash_src(src: dict) -> str:
    """Stable short hash of SRC content for cache keys and dedup."""
    s = json.dumps(src, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _validate_src(src: dict) -> tuple[bool, str]:
    """Check whether an SRC is trainable. Returns (ok, reason_if_bad).

    A valid SRC must:
      1. Have at least one loaded SQ (after robust loading).
      2. Have a scm_construct call in process.tools_called.
      3. Have at least one data_asset with an artifact_id.
      4. Pass ResearchProblem pydantic validation.
      5. Actually reconstruct as an SCMWorld (runs the pipeline).

    abstained_sq_ids are ALLOWED (valid undecidable scoring targets).
    dropped_specs are ALLOWED but logged as WARNING — a partially-broken
    SRC with 3/4 valid SQs is still scorable over those 3. At n<50 we
    cannot afford to reject every case with one malformed spec.
    """
    # 1. sub_questions_v2 must load AT LEAST ONE SQ
    sqs_raw = src.get("sub_questions_v2", [])
    if not sqs_raw:
        return False, "no sub_questions_v2"

    from sreg.models.open_investigation import load_sub_questions_v2_robust

    load_result = load_sub_questions_v2_robust(sqs_raw)
    if not load_result.loaded:
        return False, "no SQs loaded (all dropped or malformed)"
    if load_result.dropped_specs:
        logger.warning(
            "  %s specs dropped in this SRC (SQ will be abstained): %s",
            len(load_result.dropped_specs),
            sorted({d.sq_id for d in load_result.dropped_specs}),
        )

    # 2. scm_construct must exist
    has_scm = any(
        tc.get("tool") == "scm_construct"
        for tc in src.get("process", {}).get("tools_called", [])
    )
    if not has_scm:
        return False, "no scm_construct in process.tools_called"

    # 3. At least one data_asset with artifact_id
    data_assets = src.get("problem", {}).get("data_assets", [])
    if not any(a.get("artifact_id") for a in data_assets):
        return False, "no data_assets with artifact_id"

    # 4. ResearchProblem pydantic validation
    try:
        from sreg.models.research_problem import ResearchProblem

        ResearchProblem(**src["problem"])
    except Exception as e:
        return False, f"research_problem invalid: {type(e).__name__}: {e}"

    # 5. World reconstruction must actually work
    try:
        from sreg.training.env import (
            _extract_scm_construct,
            _reconstruct_world_from_args,
        )

        scm_args = _extract_scm_construct(src)
        _reconstruct_world_from_args(scm_args)
    except Exception as e:
        return False, f"world reconstruction failed: {type(e).__name__}: {e}"

    return True, "ok"


def load_srcs_from_paths(paths: list[Path]) -> list[tuple[dict, Path]]:
    """Load and validate SRCs from an explicit list of paths.

    Logs per-path outcome at INFO (ok) or WARNING (skipped) level.
    Returns only valid (src_dict, path) pairs.
    """
    valid: list[tuple[dict, Path]] = []
    for p in paths:
        p = Path(p)
        try:
            with open(p, encoding="utf-8") as f:
                src = json.load(f)
        except Exception as e:
            logger.warning("  SKIP %s: failed to parse JSON: %s", p, e)
            continue

        ok, reason = _validate_src(src)
        if not ok:
            logger.warning("  SKIP %s: %s", p.parent.name or p.stem, reason)
            continue

        valid.append((src, p))
        logger.info("  OK   %s", p.parent.name or p.stem)

    return valid


def load_srcs(src_dir: Path, pattern: str = "**/src.json") -> list[tuple[dict, Path]]:
    """Scan a directory for case-folder SRCs.

    Default pattern matches the canonical layout: `<batch>/<case>/src.json`.
    """
    src_dir = Path(src_dir)
    paths = sorted(src_dir.glob(pattern))
    logger.info("Scanning %s (pattern=%s): %d candidates", src_dir, pattern, len(paths))

    valid = load_srcs_from_paths(paths)
    logger.info("Valid SRCs: %d/%d", len(valid), len(paths))
    return valid


def _case_id(src: dict, path: Path) -> str:
    """Stable case identifier. Prefer the case folder name over world_id.

    world_id can be regenerated on reconstruction, so folder name is
    more stable for train/eval split assignment.
    """
    name = path.parent.name
    if name and name not in (".", ""):
        return name
    # Fallback: problem.world_id if folder name is unavailable
    return src.get("problem", {}).get("world_id", f"unknown_{_hash_src(src)}")


def build_dataset(
    srcs: list[tuple[dict, Path]],
    claim_cap: int = 15,
    seed: int = 42,
    n_mc: int = 20_000,
) -> Dataset:
    """Convert validated SRCs to a verifiers-compatible HF Dataset.

    Columns:
      prompt          — rendered message list (list[{role, content}])
      info            — JSON string with src_json, seed, n_mc, claim_cap, prompt_version
      task            — "oi_investigation"
      problem_id      — stable case id (folder name)
      title           — problem.title for logging
      domain          — problem.domain for logging
      src_hash        — short hash of src content (dedup, cache key)
      src_path        — absolute path (debug only)
      prompt_version  — PROMPT_VERSION (cache invalidation)
    """
    from sreg.training.prompts import render_prompt_from_src

    rows = []
    for src, path in srcs:
        prompt = render_prompt_from_src(src, claim_cap=claim_cap)

        problem = src.get("problem", {})
        info = {
            "src_json": json.dumps(src),
            "seed": seed,
            "n_mc": n_mc,
            "claim_cap": claim_cap,
            "prompt_version": PROMPT_VERSION,
        }

        rows.append(
            {
                "prompt": prompt,
                "info": json.dumps(info),
                "task": "oi_investigation",
                "problem_id": _case_id(src, path),
                "title": problem.get("title", "?"),
                "domain": problem.get("domain", "unknown"),
                "src_hash": _hash_src(src),
                "src_path": str(path.resolve()),
                "prompt_version": PROMPT_VERSION,
            }
        )

    return Dataset.from_list(rows)


def split_train_eval(
    ds: Dataset,
    eval_ids: list[str],
    id_column: str = "problem_id",
) -> tuple[Dataset, Dataset]:
    """Split dataset by explicit problem_ids. eval_ids are never in train.

    Raises ValueError if any eval_id is not present in the dataset
    (catches typos early rather than silently training on everything).
    """
    eval_set = set(eval_ids)
    available = {row[id_column] for row in ds}

    missing = eval_set - available
    if missing:
        raise ValueError(
            f"eval_ids not found in dataset: {sorted(missing)}. "
            f"Available: {sorted(available)}"
        )

    train = ds.filter(lambda row: row[id_column] not in eval_set)
    eval_ds = ds.filter(lambda row: row[id_column] in eval_set)

    logger.info(
        "Split: train=%d, eval=%d (eval_ids=%s)",
        len(train), len(eval_ds), sorted(eval_set),
    )

    return train, eval_ds


def load_from_dir(
    src_dir: Path,
    eval_ids: list[str] | None = None,
    claim_cap: int = 15,
    seed: int = 42,
    n_mc: int = 20_000,
    pattern: str = "**/src.json",
) -> Dataset | tuple[Dataset, Dataset]:
    """One-shot: scan dir, validate, build Dataset, optionally split.

    Returns a single Dataset if eval_ids is None, else (train, eval).
    """
    srcs = load_srcs(src_dir, pattern=pattern)
    if not srcs:
        raise ValueError(f"No valid SRCs found in {src_dir} (pattern={pattern})")

    ds = build_dataset(srcs, claim_cap=claim_cap, seed=seed, n_mc=n_mc)

    if eval_ids is not None:
        return split_train_eval(ds, eval_ids)
    return ds


__all__ = [
    "PROMPT_VERSION",
    "load_srcs",
    "load_srcs_from_paths",
    "build_dataset",
    "split_train_eval",
    "load_from_dir",
]
