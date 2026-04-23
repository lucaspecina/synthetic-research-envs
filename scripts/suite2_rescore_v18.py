"""Re-score v4 dump against v7 gold hygiene patches.

v7 gold hygiene patches (2026-04-19):
  - W2_F02_GOLDS (already applied in v5): PARTIAL_CORRELATION(cond_set=()) -> CORRELATION
  - SQ_F01_GOLDS: assertion POSITIVE -> DISTINGUISHABLE + polarity "distinguishable"

Justification in every case: the claim text does NOT commit to the
specific thing the old gold was asserting. `distinguishable` is the
claim-literal semantic — sign is world-truth, not claim content.

This is NOT gold-follows-compiler. It's a claim-literal audit. The
rule is: gold can only encode information explicitly in the claim
text. Any implicit world-truth must live in stage 3 (verdict), not
stage 2 (contract).

No LLM re-run needed. We re-run stage 2 / stage 3 checks against the
already-compiled v4 specs.

Outputs:
  - research/synthesis/compiler_baseline_full_dump_v18.json
  - research/synthesis/compiler_baseline_full_dump_v18.jsonl
  - research/synthesis/compiler_baseline_failures_v18.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from sreg.models.open_investigation import AtomicSpec
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS

V4_PATH = Path("research/synthesis/compiler_baseline_full_dump_v17.jsonl")
OUT_JSON = Path("research/synthesis/compiler_baseline_full_dump_v18.json")
OUT_JSONL = Path("research/synthesis/compiler_baseline_full_dump_v18.jsonl")
OUT_FAIL = Path("research/synthesis/compiler_baseline_failures_v18.json")

_ARM_KIND_ERROR_RE = re.compile(
    r"spec\[\d+\] arm_kinds: (\[.*?\]) not subset of (\[.*?\])"
)


def _gold_target_id(gt) -> str:
    return f"{gt.fact_id}_s{gt.surface_form_index}"


GOLD_BY_ID = {_gold_target_id(gt): gt for gt in ALL_GOLD_TARGETS}


def rebuild_specs(entry: dict) -> list[AtomicSpec]:
    specs_dicts = entry.get("compiler_specs") or []
    return [AtomicSpec.model_validate(d) for d in specs_dicts]


def _collect_spec_vars(spec) -> set[str]:
    vars_in = set()
    for arm in spec.arms:
        vars_in.update(arm.values.keys())
        vars_in.update(arm.condition_on.keys())
        if arm.sweep_var:
            vars_in.add(arm.sweep_var)
    if spec.measurement.target:
        t = spec.measurement.target
        if isinstance(t, str):
            vars_in.add(t)
        else:
            vars_in.update(t)
    for attr in ("lhs", "rhs", "treatment", "outcome"):
        v = getattr(spec.measurement, attr, None)
        if v:
            vars_in.add(v)
    return vars_in


def _spec_signature(spec) -> tuple:
    arm_kinds = frozenset(a.kind.value for a in spec.arms)
    return (
        arm_kinds,
        spec.measurement.kind.value,
        spec.comparison.kind.value,
        spec.assertion.kind.value,
        spec.assertion.threshold,
        spec.assertion.tolerance,
    )


def _assertion_entails(
    gold_kind, gold_thresh, gold_tol,
    comp_kind, comp_thresh, comp_tol,
) -> bool:
    """Tolerance-aware assertion entailment (verifier semantics).

    positive: val > tol. negative: val < -tol.
    greater_than(t) entails positive iff t >= gold_tol.
    less_than(t) entails negative iff t <= -gold_tol.
    Codex-verified rule (2026-04-19).
    """
    if gold_kind == comp_kind:
        return True
    if gold_kind == "positive" and comp_kind == "greater_than":
        return comp_thresh >= gold_tol
    if gold_kind == "negative" and comp_kind == "less_than":
        return comp_thresh <= -gold_tol
    return False


def _signatures_compatible(gold_sig, compiler_sig) -> bool:
    g_arms, g_meas, g_cmp, g_assert, g_thresh, g_tol = gold_sig
    c_arms, c_meas, c_cmp, c_assert, c_thresh, c_tol = compiler_sig
    if g_meas != c_meas or g_cmp != c_cmp:
        return False
    if not _assertion_entails(g_assert, g_thresh, g_tol,
                              c_assert, c_thresh, c_tol):
        return False
    _normalize = lambda s: frozenset({"intervene" if k == "adjust" else k for k in s})
    return _normalize(g_arms).issubset(_normalize(c_arms))


def _try_cover(gold_atoms, compiler_specs) -> tuple[bool, list[str]]:
    gold_sigs = [_spec_signature(a) for a in gold_atoms]
    compiler_sigs = [_spec_signature(s) for s in compiler_specs]
    used = [False] * len(compiler_sigs)
    errors: list[str] = []
    for g_idx, g_sig in enumerate(gold_sigs):
        match_idx = None
        for c_idx, c_sig in enumerate(compiler_sigs):
            if used[c_idx]:
                continue
            if _signatures_compatible(g_sig, c_sig):
                match_idx = c_idx
                break
        if match_idx is None:
            errors.append(
                f"gold atom[{g_idx}] signature {g_sig} not covered "
                f"by any compiler spec"
            )
        else:
            used[match_idx] = True
    return (not errors, errors)


def check_stage2_from_entry(gt, entry: dict) -> dict:
    """Coverage-matcher stage 2 (Codex-recommended, 2026-04-19).

    For each gold AtomicSpec (in gt.atoms or gt.alternative_atoms),
    require SOME compiler spec to match on structural signature
    (measurement, comparison, assertion kinds + arm-kinds superset).
    Extra compiler specs are accepted as auxiliaries.

    adjust ≡ intervene (both do-calculus — preserves adjust_swap
    tolerance).
    """
    if gt.status == "abstain" or not entry.get("compiler_compiled"):
        return {"pass": True, "reason": "abstain (no contract to check)"}

    try:
        specs = rebuild_specs(entry)
    except Exception as e:
        return {"pass": False, "errors": [f"spec rebuild failed: {e}"]}

    errors: list[str] = []

    if gt.atoms:
        variants = [gt.atoms] + list(getattr(gt, "alternative_atoms", []) or [])
        variant_errors = []
        coverage_ok = False
        for v_idx, variant in enumerate(variants):
            ok, v_errs = _try_cover(variant, specs)
            if ok:
                coverage_ok = True
                break
            label = "primary" if v_idx == 0 else f"alternative[{v_idx - 1}]"
            variant_errors.append((label, v_errs))
        if not coverage_ok:
            for label, v_errs in variant_errors:
                for err in v_errs:
                    errors.append(f"[{label}] {err}")

    sc = gt.structural_contract
    if sc is not None and sc.required_role_vars and specs:
        all_vars = set()
        for spec in specs:
            all_vars.update(_collect_spec_vars(spec))
        for role, var in sc.required_role_vars.items():
            if var not in all_vars:
                errors.append(f"role_var '{role}={var}' not found in specs")

    return {"pass": len(errors) == 0, "errors": errors}


def is_adjust_swap(stage2_errors: list[str]) -> bool:
    """Mirrors suite2_full_dump_v4.py exactly (strict version)."""
    if not stage2_errors:
        return False
    for err in stage2_errors:
        m = _ARM_KIND_ERROR_RE.search(err)
        if not m:
            return False
        got_literal, allowed_literal = m.group(1), m.group(2)
        try:
            got = set(json.loads(got_literal.replace("'", '"')))
            allowed = set(json.loads(allowed_literal.replace("'", '"')))
        except Exception:
            return False
        if got != {"adjust"}:
            return False
        if "intervene" not in allowed:
            return False
    return True


def bucket_of(s1_ok: bool, s2: dict, s3: dict) -> str:
    if not s1_ok:
        return "stage1_fail"
    if not s3.get("pass"):
        return "verdict_wrong"
    if s2.get("pass"):
        return "full_pass"
    errors = s2.get("errors") or []
    if is_adjust_swap(errors):
        return "adjust_swap"
    return "real_struct_err"


def main() -> None:
    entries = [
        json.loads(line)
        for line in V4_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    out_entries = []
    changed = []
    for entry in entries:
        eid = entry["id"]
        gt = GOLD_BY_ID.get(eid)
        if gt is None:
            out_entries.append(entry)
            continue

        new_s2 = check_stage2_from_entry(gt, entry)
        s1_ok = entry.get("stage1_ok", False)
        s3 = entry.get("stage3", {})
        new_bucket = bucket_of(s1_ok, new_s2, s3)

        new_entry = dict(entry)
        if new_bucket != entry.get("category") or new_s2 != entry.get("stage2"):
            new_entry["stage2"] = new_s2
            new_entry["category"] = new_bucket
            changed.append({
                "id": eid,
                "old_category": entry.get("category"),
                "new_category": new_bucket,
                "old_stage2_errors": entry.get("stage2", {}).get("errors", []),
                "new_stage2_errors": new_s2.get("errors", []),
            })
        out_entries.append(new_entry)

    OUT_JSON.write_text(json.dumps(out_entries, indent=2), encoding="utf-8")
    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for e in out_entries:
            f.write(json.dumps(e) + "\n")

    fails = [e for e in out_entries if e["category"] not in ("full_pass", "adjust_swap")]
    OUT_FAIL.write_text(json.dumps(fails, indent=2), encoding="utf-8")

    counts = Counter(e["category"] for e in out_entries)
    n = len(out_entries)

    print("=" * 60)
    print("v18 rescore (v11 LLM dump + coverage-matcher + new prompts)")
    print("=" * 60)
    for cat in ("full_pass", "adjust_swap", "real_struct_err", "verdict_wrong", "stage1_fail"):
        c = counts.get(cat, 0)
        print(f"  {cat:20s} {c:3d}  ({c/n*100:4.1f}%)")
    effective = counts.get("full_pass", 0) + counts.get("adjust_swap", 0)
    strict = counts.get("full_pass", 0)
    print()
    print(f"  strict_full_pass_rate  = {strict}/{n} = {strict/n*100:.1f}%")
    print(f"  effective_pass_rate    = {effective}/{n} = {effective/n*100:.1f}%")
    print()
    print(f"Changed categorizations: {len(changed)}")
    for c in changed:
        print(f"  {c['id']}: {c['old_category']} -> {c['new_category']}")
    print()
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_JSONL}")
    print(f"Wrote {OUT_FAIL}  ({len(fails)} entries)")


if __name__ == "__main__":
    main()
