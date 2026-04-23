"""Full per-target dump for Suite 2 — v4 (post refined abstention (narrow to pure structural-role) (2026-04-19)).

v8 measures the effect of Recipe J (changepoint/piecewise) + Recipe G-simple
clarification on top of v4 baseline (2026-04-19 push for 90%):
  - v3 cumulative (Tasks #1/#2/#3/#6): abstention exemplars in Flow A,
    QueryArm validator, TARGETED_RECIPE C-F.
  - v4 delta (Task #3.5): Recipe G (total/direct effect via 4-arm
    contrast_diff) + three "wrong → right" exemplars for the escape
    hatches seen at v3:
      * condition → intervene for treated/untreated variance claims.
      * distinguishable → positive/negative for "X causes Y" claims.
      * partial_correlation → identifiability_check for collider / id.
  - Prompt growth from v3: +5k chars (~1.2k tokens).

Outputs:
  - research/synthesis/compiler_baseline_full_dump_v17.json
  - research/synthesis/compiler_baseline_failures_v17.json
  - research/synthesis/compiler_baseline_full_dump_v17.jsonl (streaming log)

v2 artifacts remain as the pre-fix baseline (2026-04-17 snapshot).

Serialization uses `spec.model_dump(mode='json')` so the full AtomicSpec
(arm.treatment, arm.outcome, arm.adjust_set, arm.sweep_*, measurement.*
fields, assertion.tolerance, condition_on predicates) round-trips cleanly.
Guarded by `tests/models/test_open_investigation.py::TestAtomicSpecRoundTrip`.

Categories (mirrors `suite2_compiler_baseline.md` §2 rubric):

  stage1_fail      stage 1 wrong (abstained when should compile, or vice versa)
  verdict_wrong    stage 1 ok, stage 3 wrong
  full_pass        stages 1+2+3 all ok
  adjust_swap      stages 1+3 ok; stage 2 fails ONLY on arm_kinds where the
                   compiler used `adjust` and the contract required `intervene`
  real_struct_err  stages 1+3 ok; stage 2 fails on something else

Cost: 55 LLM calls (Azure gpt-5.4, temperature=0). Runtime ~5-10 min.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from sreg.inference.openai_client import OpenAIClient
from sreg.inference.protocol import Message, MessageRole
from sreg.models.open_investigation import (
    AtomicSpec,
    ClaimCard,
    EvidenceRef,
)
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import build_world_summary
from sreg.tools.oi_extraction import compile_claim
from sreg.tools.oi_verifier import verify_atom

from tests.eval.suite2_translation.fact_tables import ALL_FACTS, Verdict
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS
from tests.eval.suite2_translation.worlds import ALL_WORLDS

FACT_BY_ID = {f.fact_id: f for f in ALL_FACTS}
WORLD_FOR_FACT = {f.fact_id: f.world for f in ALL_FACTS}

OUT_FULL = Path("research/synthesis/compiler_baseline_full_dump_v17.json")
OUT_FAILS = Path("research/synthesis/compiler_baseline_failures_v17.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_llm_call(client):
    def llm_call(*args):
        if len(args) == 2 and isinstance(args[0], str):
            system, user = args
            msgs = [
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user),
            ]
        elif len(args) == 1 and isinstance(args[0], list):
            msgs = [
                Message(role=MessageRole(m["role"]), content=m["content"])
                for m in args[0]
            ]
        else:
            raise TypeError(f"Unexpected args: {type(args)}")
        resp = client.chat(msgs, temperature=0.0)
        return resp.message.content or ""
    return llm_call


def infer_target(gt, fact) -> str:
    if gt.structural_contract and gt.structural_contract.required_role_vars:
        rv = gt.structural_contract.required_role_vars
        if "outcome" in rv:
            return rv["outcome"]
        if "rhs" in rv:
            return rv["rhs"]
    wk = WORLD_FOR_FACT.get(fact.fact_id, "")
    if "w1" in wk:
        return "Y"
    if "w2" in wk:
        return "D"
    if "w3" in wk:
        return "H"
    return "Y"


def spec_to_json(spec: AtomicSpec) -> dict:
    """Round-trip-safe serialization. Guarded by TestAtomicSpecRoundTrip."""
    payload = spec.model_dump(mode="json")
    # Stabilize non-deterministic containers (frozenset observed_vars).
    for arm in payload.get("arms", []):
        if arm.get("observed_vars") is not None:
            arm["observed_vars"] = sorted(arm["observed_vars"])
    return payload


# ---------------------------------------------------------------------------
# Stage evaluators (mirror tests/eval/suite2_translation/test_compiler_llm.py)
# ---------------------------------------------------------------------------

def check_stage1(gt, compiler_out) -> bool:
    if gt.status == "compile":
        return compiler_out.compiled
    return not compiler_out.compiled


def check_stage2(gt, compiler_out) -> dict:
    if gt.status == "abstain" or not compiler_out.compiled:
        return {"pass": True, "reason": "abstain (no contract to check)"}

    sc = gt.structural_contract
    if sc is None:
        return {"pass": True, "reason": "no contract defined"}

    specs = compiler_out.specs
    errors: list[str] = []

    if isinstance(sc.n_atoms, int):
        if len(specs) != sc.n_atoms:
            errors.append(f"n_atoms: expected {sc.n_atoms}, got {len(specs)}")
    elif isinstance(sc.n_atoms, tuple):
        lo, hi = sc.n_atoms
        if not (lo <= len(specs) <= hi):
            errors.append(f"n_atoms: expected {lo}-{hi}, got {len(specs)}")

    for i, spec in enumerate(specs):
        arm_kinds = {a.kind.value for a in spec.arms}
        if not arm_kinds.issubset(sc.allowed_arm_kinds):
            errors.append(
                f"spec[{i}] arm_kinds: {sorted(arm_kinds)} not subset of "
                f"{sorted(sc.allowed_arm_kinds)}"
            )
        if spec.measurement.kind.value != sc.required_measurement_kind:
            errors.append(
                f"spec[{i}] measurement: {spec.measurement.kind.value} "
                f"!= {sc.required_measurement_kind}"
            )
        if spec.comparison.kind.value != sc.required_comparison_kind:
            errors.append(
                f"spec[{i}] comparison: {spec.comparison.kind.value} "
                f"!= {sc.required_comparison_kind}"
            )
        if spec.assertion.kind.value != sc.required_assertion_polarity:
            errors.append(
                f"spec[{i}] assertion: {spec.assertion.kind.value} "
                f"!= {sc.required_assertion_polarity}"
            )

    if sc.required_role_vars and specs:
        all_vars = set()
        for spec in specs:
            for arm in spec.arms:
                all_vars.update(arm.values.keys())
                all_vars.update(arm.condition_on.keys())
            if spec.measurement.target:
                t = spec.measurement.target
                if isinstance(t, str):
                    all_vars.add(t)
                else:
                    all_vars.update(t)
            for attr in ("lhs", "rhs", "treatment", "outcome"):
                v = getattr(spec.measurement, attr, None)
                if v:
                    all_vars.add(v)
        for role, var in sc.required_role_vars.items():
            if var not in all_vars:
                errors.append(f"role_var '{role}={var}' not found in specs")

    return {"pass": len(errors) == 0, "errors": errors}


def check_stage3(gt, compiler_out, fact, world, solver) -> dict:
    if gt.status == "abstain" or not compiler_out.compiled:
        return {"pass": True, "reason": "abstain (no verdict to check)"}

    verdicts = []
    for spec in compiler_out.specs:
        v = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        verdicts.append(v)

    all_hold = all(v.solver_assertion_holds for v in verdicts)
    any_fail = any(not v.solver_assertion_holds for v in verdicts)

    if fact.truth_value == Verdict.TRUE:
        ok = all_hold
    elif fact.truth_value == Verdict.FALSE:
        ok = any_fail
    elif fact.truth_value == Verdict.NOT_IDENTIFIABLE:
        ok = all_hold
    else:
        ok = False

    return {
        "pass": ok,
        "expected_truth": fact.truth_value.value if fact.truth_value else None,
        "all_hold": all_hold,
        "any_fail": any_fail,
        "verdicts": [
            {
                "atom_id": v.atom_id,
                "holds": bool(v.solver_assertion_holds),
                "ground_truth": (
                    v.ground_truth if isinstance(v.ground_truth, (bool, int, float, str))
                    else str(v.ground_truth)
                ) if v.ground_truth is not None else None,
                "detail": (str(v.detail)[:300] if v.detail else None),
            }
            for v in verdicts
        ],
    }


# ---------------------------------------------------------------------------
# Bucketing: adjust_swap detection
# ---------------------------------------------------------------------------

_ARM_KIND_ERROR_RE = re.compile(
    r"spec\[\d+\] arm_kinds: (\[.*?\]) not subset of (\[.*?\])"
)


def is_adjust_swap(stage2_errors: list[str]) -> bool:
    """Stage 2 errors come from arm_kind mismatch, and the *only* mismatch is
    that the compiler emitted `adjust` where the contract required `intervene`.

    Conservative: require (a) every error is an arm_kind error, and (b) every
    arm_kind error is exactly `['adjust']` vs a contract set that contains
    `intervene` (possibly with other kinds). If anything else is off —
    measurement / comparison / assertion / role_var / n_atoms / other arm_kind —
    it's a real structural error, not adjust_swap.
    """
    if not stage2_errors:
        return False
    for err in stage2_errors:
        m = _ARM_KIND_ERROR_RE.search(err)
        if not m:
            return False
        got_literal, allowed_literal = m.group(1), m.group(2)
        # Parse literal lists like "['adjust']" and "['intervene', 'condition']"
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
    if not s3["pass"]:
        return "verdict_wrong"
    if s2["pass"]:
        return "full_pass"
    errors = s2.get("errors", [])
    if is_adjust_swap(errors):
        return "adjust_swap"
    return "real_struct_err"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    client = OpenAIClient()
    llm_call = make_llm_call(client)

    solver_cache: dict[str, tuple] = {}
    summary_cache: dict[tuple[str, str], object] = {}

    def get_world_solver(wk: str):
        if wk not in solver_cache:
            w = ALL_WORLDS[wk]
            solver_cache[wk] = (w, SCMSolver(w, n_mc=50_000))
        return solver_cache[wk]

    def get_summary(wk: str, target: str):
        k = (wk, target)
        if k not in summary_cache:
            summary_cache[k] = build_world_summary(ALL_WORLDS[wk], target)
        return summary_cache[k]

    # Deterministic iteration order for reproducibility
    ordered_targets = sorted(
        ALL_GOLD_TARGETS, key=lambda g: (g.fact_id, g.surface_form_index)
    )

    entries: list[dict] = []
    t0 = time.time()

    # Stream to JSONL for resumability / diagnosability.
    stream_path = OUT_FULL.with_suffix(".jsonl")
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    stream_f = stream_path.open("w", encoding="utf-8")

    for i, gt in enumerate(ordered_targets, start=1):
        fact = FACT_BY_ID.get(gt.fact_id)
        if fact is None:
            print(f"[{i}/{len(ordered_targets)}] skip {gt.fact_id}: no fact")
            continue

        wk = WORLD_FOR_FACT[gt.fact_id]
        sf = fact.surface_forms[gt.surface_form_index]
        target = infer_target(gt, fact)
        summary = get_summary(wk, target)
        world, solver = get_world_solver(wk)

        focus = []
        if gt.structural_contract and gt.structural_contract.required_role_vars:
            focus = list(set(gt.structural_contract.required_role_vars.values()))
        if not focus:
            focus = ["Y"]

        entry_id = f"{gt.fact_id}_s{gt.surface_form_index}"

        claim = ClaimCard(
            claim_id=entry_id,
            claim_text=sf.text,
            focus_variables=focus,
            confidence=1.0,
            evidence_basis=[EvidenceRef(
                artifact_id="gold_eval",
                rationale="Gold standard evaluation for compiler testing",
            )],
        )

        call_t0 = time.time()
        try:
            cout = compile_claim(claim, summary, llm_call=llm_call)
            call_err = None
        except Exception as e:
            cout = None
            call_err = f"{type(e).__name__}: {e}"
        call_dt = time.time() - call_t0

        if call_err is not None or cout is None:
            entry = {
                "id": entry_id,
                "fact_id": gt.fact_id,
                "world": wk,
                "difficulty": sf.difficulty,
                "claim": sf.text,
                "truth_value": fact.truth_value.value if fact.truth_value else None,
                "gold_status": gt.status,
                "category": "stage1_fail",
                "error": call_err or "compile_claim returned None",
                "llm_call_seconds": round(call_dt, 2),
                "compiler_specs": [],
                "gold_specs": [spec_to_json(s) for s in gt.atoms],
                "stage1_ok": False,
                "stage2": {"pass": False, "errors": ["compile exception"]},
                "stage3": {"pass": False, "reason": "compile exception"},
            }
        else:
            s1_ok = check_stage1(gt, cout)
            s2 = check_stage2(gt, cout)
            if s1_ok and cout.compiled:
                s3 = check_stage3(gt, cout, fact, world, solver)
            else:
                s3 = {"pass": True, "reason": "stage1 fail or no specs"}

            category = bucket_of(s1_ok, s2, s3)

            entry = {
                "id": entry_id,
                "fact_id": gt.fact_id,
                "world": wk,
                "difficulty": sf.difficulty,
                "claim": sf.text,
                "truth_value": fact.truth_value.value if fact.truth_value else None,
                "gold_status": gt.status,
                "category": category,
                "llm_call_seconds": round(call_dt, 2),
                "compiler_specs": [spec_to_json(s) for s in cout.specs] if cout.compiled else [],
                "gold_specs": [spec_to_json(s) for s in gt.atoms],
                "stage1_ok": s1_ok,
                "stage2": s2,
                "stage3": s3,
                "backend": cout.units[0].backend if cout.units else None,
                "compiler_compiled": cout.compiled,
                "compiler_abstain_reason": cout.abstention_reason,
                "deliberate_abstention": cout.deliberate_abstention,
            }

        entries.append(entry)
        stream_f.write(json.dumps(entry, default=str) + "\n")
        stream_f.flush()

        elapsed = time.time() - t0
        print(
            f"[{i:2d}/{len(ordered_targets)}] {entry_id:15s} "
            f"bucket={entry['category']:15s} "
            f"dt={call_dt:5.1f}s elapsed={elapsed:6.1f}s",
            flush=True,
        )

    stream_f.close()

    # Write final full dump
    OUT_FULL.write_text(json.dumps(entries, indent=2, sort_keys=True, default=str), encoding="utf-8")
    # Derive failures (anything other than full_pass / adjust_swap).
    fail_entries = [e for e in entries if e["category"] not in ("full_pass", "adjust_swap")]
    OUT_FAILS.write_text(
        json.dumps(fail_entries, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    # Summary
    from collections import Counter
    counts = Counter(e["category"] for e in entries)
    n = len(entries)
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for cat in ("full_pass", "adjust_swap", "real_struct_err", "verdict_wrong", "stage1_fail"):
        c = counts.get(cat, 0)
        pct = (c / n * 100) if n else 0
        print(f"  {cat:18s} {c:3d}  ({pct:4.1f}%)")
    effective = counts.get("full_pass", 0) + counts.get("adjust_swap", 0)
    strict = counts.get("full_pass", 0)
    print()
    print(f"  strict_full_pass_rate  = {strict}/{n} = {strict/n*100:.1f}%")
    print(f"  effective_pass_rate    = {effective}/{n} = {effective/n*100:.1f}%")
    print()

    # Honesty metric: for gold-abstain targets, count deliberate vs fallback.
    gold_abstains = [e for e in entries if e["gold_status"] == "abstain"]
    ok_abstains = [e for e in gold_abstains if e.get("stage1_ok")]
    deliberate = [e for e in ok_abstains if e.get("deliberate_abstention")]
    fallback = [e for e in ok_abstains if not e.get("deliberate_abstention")]
    compile_targets = [e for e in entries if e["gold_status"] == "compile"]
    comp_deliberate_miss = [
        e for e in compile_targets
        if not e.get("stage1_ok") and e.get("deliberate_abstention")
    ]
    print("Abstention honesty (gold_status='abstain'):")
    print(f"  correct_abstain        = {len(ok_abstains)}/{len(gold_abstains)}")
    print(f"    deliberate           = {len(deliberate)}")
    print(f"    fallback (lucky)     = {len(fallback)}")
    print("Over-abstention (gold_status='compile' but compiler abstained deliberately):")
    print(f"  deliberate_over_abstain = {len(comp_deliberate_miss)}/{len(compile_targets)}")
    print()
    print(f"Wrote {OUT_FULL}")
    print(f"Wrote {OUT_FAILS}  ({len(fail_entries)} entries)")
    print(f"Stream log: {stream_path}")


if __name__ == "__main__":
    main()
