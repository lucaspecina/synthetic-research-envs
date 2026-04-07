#!/usr/bin/env python
"""P06 Phase C forensics: A + B + C diagnostics (read-only).

Reads baseline + paired oi_result.json for a fixed set of cases and
extracts signals to distinguish hypotheses H1-H4 about the emergent
fabrication and force-submit confounds.

Diagnostic A (fabrication forensics):
  For each claim in the 3 broken paired cases, record:
    - artifact_id cited
    - was it in trace.accesses
    - was there a save_artifact preceding it
    - rationale text + keyword category (dataset/analysis/regression/step)
  Core question: confusing "evidence source" with "analytical step"?

Diagnostic B (force-submit forensics):
  For each case, record:
    - n_python_exec / n_think / n_submit_claims
    - iteration of first "claim-like summary" in assistant text
    - cluster of micro-python_exec at end
    - n_claims finally submitted
  Core question: out of time thinking, writing, or contract hardness?

Diagnostic C (submit-path inspection):
  Last 2-3 assistant messages + tool calls before submit for 3 broken + 1 clean.
  Used to distinguish H1-H4 pattern.

Output: JSON + summary text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BROKEN_CASES = ["chemical", "confounding", "immunotherapy"]
CLEAN_CASE = "competing_mech"
ALL_FORENSIC_CASES = BROKEN_CASES + [CLEAN_CASE]

KEYWORDS = {
    "dataset": ["dataset", "data", "rows", "records", "observations", "dataframe", "table", "sample"],
    "analysis": ["analysis", "analyzed", "computed", "calculated", "examined"],
    "regression": ["regression", "ols", "coefficient", "fit", "model", "coef", "r-squared", "pvalue", "p-value", "adjusted"],
    "step": ["step", "code", "execution", "python_exec", "run", "ran", "executed"],
}


def _load(path: Path) -> dict:
    return json.load(open(path, encoding="utf-8"))


def _classify_rationale(text: str) -> list[str]:
    """Return list of keyword categories present in rationale text."""
    t = text.lower()
    hits = []
    for cat, kws in KEYWORDS.items():
        if any(kw in t for kw in kws):
            hits.append(cat)
    return hits


def _diagnostic_a(case: str, baseline_dir: Path, paired_dir: Path) -> dict:
    """A: fabrication forensics per case, paired vs baseline."""
    def _case_snapshot(oi_path: Path) -> dict:
        d = _load(oi_path)
        si = d.get("score_inputs_v2", {})
        claims = si.get("claims", [])
        trace = si.get("trace", {})
        accessed = set()
        save_artifact_ids = set()
        for acc in trace.get("accesses", []):
            aid = acc.get("artifact_id", "")
            accessed.add(aid)
            if acc.get("access_type") == "analyze" and aid.startswith("derived_"):
                save_artifact_ids.add(aid)

        claim_rows = []
        for c in claims:
            eb = c.get("evidence_basis", []) or []
            for ref in eb:
                aid = ref.get("artifact_id", "")
                rat = ref.get("rationale", "") or ""
                claim_rows.append({
                    "claim_id": c.get("claim_id"),
                    "claim_text_excerpt": (c.get("claim_text", "") or "")[:160],
                    "artifact_id": aid,
                    "is_python_exec": aid == "python_exec",
                    "in_trace": aid in accessed,
                    "rationale_excerpt": rat[:200],
                    "rationale_categories": _classify_rationale(rat),
                })
        return {
            "n_claims": len(claims),
            "accessed_artifacts": sorted(accessed),
            "save_artifact_count": len(save_artifact_ids),
            "claim_refs": claim_rows,
        }

    return {
        "baseline": _case_snapshot(baseline_dir / case / "oi_result.json"),
        "paired": _case_snapshot(paired_dir / case / "oi_result.json"),
    }


def _diagnostic_b(case: str, baseline_dir: Path, paired_dir: Path) -> dict:
    """B: force-submit forensics — iteration-level breakdown."""
    def _case_snapshot(oi_path: Path) -> dict:
        d = _load(oi_path)
        msgs = d.get("conversation", [])

        # Tool-call counts per type, and their iteration index
        tool_calls = []
        for i, m in enumerate(msgs):
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    tool_calls.append({
                        "msg_idx": i,
                        "name": tc.get("function", {}).get("name", ""),
                        "args_len": len(str(tc.get("function", {}).get("arguments", ""))),
                    })

        # Force-submit detection
        force_submit = any(
            "MUST call submit_claims NOW" in str(m.get("content", ""))
            or "exhausted all iterations" in str(m.get("content", ""))
            for m in msgs
        )

        # First iteration with claim-like summary in assistant text
        first_claim_like_idx = None
        for i, m in enumerate(msgs):
            if m.get("role") == "assistant":
                txt = str(m.get("content", "") or "")
                if any(kw in txt.lower() for kw in [
                    "finding", "claim", "result", "summary", "conclude",
                ]) and len(txt) > 100:
                    first_claim_like_idx = i
                    break

        # Counts by tool name
        n_python = sum(1 for tc in tool_calls if tc["name"] == "python_exec")
        n_think = sum(1 for tc in tool_calls if tc["name"] == "think")
        n_submit = sum(1 for tc in tool_calls if tc["name"] == "submit_claims")

        # Micro python_exec at the end: len(args) < 500 chars in the last third
        if tool_calls:
            split = int(len(tool_calls) * 2 / 3)
            tail = tool_calls[split:]
            n_micro_tail = sum(
                1 for tc in tail
                if tc["name"] == "python_exec" and tc["args_len"] < 500
            )
        else:
            n_micro_tail = 0

        # Iteration index (msg_idx) of the submit
        submit_msg_idx = None
        for tc in tool_calls:
            if tc["name"] == "submit_claims":
                submit_msg_idx = tc["msg_idx"]
                break

        return {
            "n_msgs": len(msgs),
            "n_python_exec": n_python,
            "n_think": n_think,
            "n_submit_claims": n_submit,
            "force_submit": force_submit,
            "first_claim_like_msg_idx": first_claim_like_idx,
            "submit_msg_idx": submit_msg_idx,
            "n_micro_python_tail": n_micro_tail,
        }

    return {
        "baseline": _case_snapshot(baseline_dir / case / "oi_result.json"),
        "paired": _case_snapshot(paired_dir / case / "oi_result.json"),
    }


def _diagnostic_c(case: str, paired_dir: Path) -> dict:
    """C: submit-path — last 3 assistant+tool before submit, paired only."""
    d = _load(paired_dir / case / "oi_result.json")
    msgs = d.get("conversation", [])

    # Find submit msg index
    submit_idx = None
    for i, m in enumerate(msgs):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                if tc.get("function", {}).get("name") == "submit_claims":
                    submit_idx = i
                    break
            if submit_idx is not None:
                break

    if submit_idx is None:
        return {"error": "no submit found"}

    # Collect last 6 messages before submit (3 assistant + 3 tool) and submit itself
    start = max(0, submit_idx - 8)
    window = []
    for i in range(start, min(submit_idx + 2, len(msgs))):
        m = msgs[i]
        entry = {
            "idx": i,
            "role": m.get("role"),
            "content_excerpt": (str(m.get("content", "") or ""))[:500],
        }
        if m.get("tool_calls"):
            entry["tool_calls"] = [
                {
                    "name": tc.get("function", {}).get("name", ""),
                    "args_excerpt": (str(tc.get("function", {}).get("arguments", "") or ""))[:500],
                }
                for tc in m["tool_calls"]
            ]
        window.append(entry)

    return {"submit_msg_idx": submit_idx, "window": window}


def main():
    baseline = Path("results/p05_canonical_batch")
    paired = Path("results/p06_paired")

    forensics = {
        "A_fabrication": {},
        "B_force_submit": {},
        "C_submit_path": {},
    }

    for case in ALL_FORENSIC_CASES:
        forensics["A_fabrication"][case] = _diagnostic_a(case, baseline, paired)

    # Diagnostic B on all 12 cases + highlight baseline vs paired force-submit changes
    for case in [
        "chemical", "competing_mech", "confounding", "coral_bleach",
        "heterogeneity", "identifiability", "immunotherapy", "microbiome",
        "missing_data", "policy_equity", "poverty", "selection_bias",
    ]:
        forensics["B_force_submit"][case] = _diagnostic_b(case, baseline, paired)

    # Diagnostic C on 3 broken + 1 clean
    for case in ALL_FORENSIC_CASES:
        forensics["C_submit_path"][case] = _diagnostic_c(case, paired)

    out_path = Path("results/p06_paired/forensics.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(forensics, f, indent=2)
    print(f"saved: {out_path}")

    # ------------------------------------------------------------------
    # Quick summary to console
    # ------------------------------------------------------------------
    print()
    print("=" * 90)
    print("  A: FABRICATION FORENSICS")
    print("=" * 90)
    for case in ALL_FORENSIC_CASES:
        d = forensics["A_fabrication"][case]
        bp = d["paired"]
        bb = d["baseline"]
        n_fab_p = sum(1 for r in bp["claim_refs"] if r["is_python_exec"])
        n_fab_b = sum(1 for r in bb["claim_refs"] if r["is_python_exec"])
        print(f"\n  [{case}]")
        print(f"    baseline: n_claims={bb['n_claims']} "
              f"save_artifact={bb['save_artifact_count']} "
              f"fab_refs={n_fab_b}")
        print(f"    paired:   n_claims={bp['n_claims']} "
              f"save_artifact={bp['save_artifact_count']} "
              f"fab_refs={n_fab_p}")
        print(f"    accessed paired: {bp['accessed_artifacts']}")

        # Show rationale categories for fabricated paired claims
        if n_fab_p > 0:
            cats = {}
            for r in bp["claim_refs"]:
                if r["is_python_exec"]:
                    for c in r["rationale_categories"]:
                        cats[c] = cats.get(c, 0) + 1
            print(f"    paired fab rationale cats: {cats}")

    print()
    print("=" * 90)
    print("  B: FORCE-SUBMIT FORENSICS")
    print("=" * 90)
    print(f"\n  {'case':<16} {'n_py b/p':>10} {'force b/p':>12} {'micro_tail b/p':>16} {'first_claim b/p':>18}")
    for case, d in forensics["B_force_submit"].items():
        b = d["baseline"]
        p = d["paired"]
        fcb = b["first_claim_like_msg_idx"]
        fcp = p["first_claim_like_msg_idx"]
        print(f"  {case:<16} "
              f"{b['n_python_exec']}/{p['n_python_exec']:<8} "
              f"{'Y' if b['force_submit'] else '.'}/{'Y' if p['force_submit'] else '.':<10} "
              f"{b['n_micro_python_tail']}/{p['n_micro_python_tail']:<14} "
              f"{str(fcb) or '-'}/{str(fcp) or '-'}")

    print()
    print("=" * 90)
    print("  C: SUBMIT-PATH INSPECTION (see forensics.json for full)")
    print("=" * 90)
    for case in ALL_FORENSIC_CASES:
        d = forensics["C_submit_path"][case]
        if "error" in d:
            print(f"  [{case}] {d['error']}")
            continue
        print(f"  [{case}] submit at msg {d['submit_msg_idx']}, "
              f"window size={len(d['window'])}")


if __name__ == "__main__":
    main()
