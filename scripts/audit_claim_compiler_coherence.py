"""Claim compiler (Flow A) semantic coherence audit.

Mirrors audit_sq_text_spec_coherence.py but for Flow A (claim -> compiler_specs).

Input:
    research/synthesis/compiler_baseline_full_dump_v2.json (55 entries)

For each entry: judge whether compiler_specs semantically cover the claim text.
Uses the same 7-category rubric as the SQ audit.

Optional --include-gold flag audits gold_specs in parallel as a sanity control
(gold should be ~100% coherent; if not, the rubric itself has drift).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sreg.inference.openai_client import OpenAIClient
from sreg.inference.protocol import Message, MessageRole


SEVERE_VERDICTS = {"wrong_claim", "contradictory", "orphan_vars"}
LOW_CONFIDENCE_THRESHOLD = 0.6


# -------------------------------------------------------------------
# Per-world variable glossaries (from tests/eval/suite2_translation/worlds.py)
# -------------------------------------------------------------------

WORLD_GLOSSARIES: dict[str, dict[str, Any]] = {
    "w1_comparative_effectiveness": {
        "description": (
            "Clinical medicine — observational study of treatment effectiveness. "
            "Linear-Gaussian except Y has interaction term B*T."
        ),
        "variables": {
            "A": "age (root, exogenous)",
            "S": "severity (confounder of T and Y)",
            "T": "treatment (the main exposure)",
            "M": "compliance (mediator on T->Y)",
            "B": "biomarker (effect modifier via B*T interaction, independent root)",
            "Y": "primary outcome",
            "SE": "side_effect (secondary outcome)",
        },
        "edges": "A->S->T->M->Y; A->Y; A->SE; S->Y; T->Y; T->SE; B->Y; B*T->Y",
        "canonical_claim_targets": "T->Y (treatment->outcome), T->SE (treatment->side_effect)",
    },
    "w2_observational_epidemiology": {
        "description": (
            "Epidemiological study with Simpson's reversal: crude E~D "
            "correlation has OPPOSITE sign from true causal effect."
        ),
        "variables": {
            "C": "confounder (root, affects E and D)",
            "I": "upstream instrument (root, affects only E)",
            "E": "exposure (main exposure)",
            "M": "mediator on E->D",
            "D": "disease (primary outcome)",
            "L": "collider on E->L<-D (DO NOT adjust for L)",
        },
        "edges": "C->E, C->D, I->E, E->M->D, E->D, E->L<-D",
        "canonical_claim_targets": "E->D (exposure->disease)",
    },
    "w3_environmental_health": {
        "description": (
            "Environmental health — includes latent confounder U, piecewise "
            "threshold f(Temp), and WindSpeed (null variable with no effect)."
        ),
        "variables": {
            "R": "region (root)",
            "U": "hidden confounder (LATENT, unobservable)",
            "Temp": "temperature (direct + threshold effect on H)",
            "P": "pollution (P->H NOT identifiable because U is latent)",
            "W": "water_quality (mediator)",
            "H": "health (primary outcome)",
            "WindSpeed": "NULL variable (no effect on anything; disconnected)",
        },
        "edges": "R->Temp, R->P, U->P, U->H, Temp->W->H, P->W, P->H, Temp->H (piecewise)",
        "canonical_claim_targets": (
            "Temp->H (threshold), P->H (NOT identifiable), WindSpeed->H (null)"
        ),
    },
}


SYSTEM_PROMPT = """You are a semantic-coherence auditor for a scientific
evaluation system. For each input you receive:

1. A `claim` in natural language (one sentence, scientific domain).
2. A `world` name + variable glossary (which canonical variables exist and
   what they mean in the domain).
3. A list of `compiler_specs` (what the compiler produced from the claim).
   Each spec has:
   - arms: list of query scenarios (kind, treatment, outcome, adjust_set,
     values, observed_vars)
   - measurement: what quantity to compute (kind, target, lhs/rhs, etc.)
   - comparison: how to compare measurements across arms (kind, ref_arm)
   - assertion: what should hold (kind: positive, negative, near_zero,
     distinguishable, identifiable, ...)

Your job: decide whether the spec set *semantically* covers what the claim
asks. Map natural-language terms to canonical variable names using the
glossary (e.g., "treatment" -> T, "outcome" -> Y). Use this rubric (entry
can match multiple; lower severity first):

- coherent: specs measure what the claim asks (no missing dimension).
- narrow: claim is broad but specs cover only a subset (miss a dimension
  the claim explicitly requests).
- incomplete: claim has 2+ distinct subclaims; specs cover only some.
- wrong_claim: a spec measures a different thing than the claim asks
  (e.g., claim asks direction, spec asks distinguishability).
- orphan_vars: variables mentioned in the claim are absent in specs, or
  specs involve vars not mentioned in the claim.
- contradictory: specs within the same entry contradict each other
  (opposite assertions on the same thing, or incompatible measurements).
- abstain: not enough information to judge; the coupling is unclear.

HARD RULES:
- Every violation must cite evidence: spec_id + specific field
  (arm/measurement/comparison/assertion) + exact variable names.
- If evidence is weak, use `abstain` with low confidence. Do NOT invent.
- `coherent` means nothing extra is needed; only use when the set cleanly
  covers the claim.
- A claim like "Does X affect Y?" asks direction/existence of effect;
  a spec with assertion=distinguishable only tests "different from zero"
  which is coherent for this style of claim. But "X increases Y" or
  "X causes Y" with quantitative direction needs assertion=positive/negative
  or a signed comparison.
- Identifiability claims ("is X's effect identifiable?" or "no adjustment
  set suffices") are DIFFERENT from effect-direction claims. Flag as
  wrong_claim if the spec measures a direction when the claim asks
  identifiability or vice-versa.

OUTPUT: a single JSON object, no prose, matching this schema:
{
  "verdict": "<primary label>",
  "violations": [
    {
      "category": "<label>",
      "reason": "<one sentence>",
      "evidence": {"spec_ids": ["..."], "fields": ["..."], "variables": ["..."]}
    }
  ],
  "confidence": <float 0..1>
}

Few-shot examples:

EX1 (wrong_claim):
  claim: "Does drug X reduce mortality compared to drug Y?"
  spec summary: arms=[intervene X=1, intervene Y=1], measurement=mean(mortality),
    comparison=difference, assertion=distinguishable
  verdict: wrong_claim (claim asks for direction "reduce" but assertion is
    distinguishable which only tests "different"). cite assertion field on
    that spec_id.

EX2 (orphan_vars):
  claim: "Does X cause Y controlling for Z?"
  world variables: {X, Y, Z, W}
  spec summary: arms=[kind=adjust, treatment=X, outcome=Y, adjust_set=[]],
    measurement=mean(Y), assertion=positive
  verdict: orphan_vars (Z mentioned in claim but not used in any adjust_set).
    cite adjust_set field + variable Z.
"""


def _format_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Compact spec summary for LLM consumption (keep only semantic fields)."""
    arms_out = []
    for a in spec.get("arms", []) or []:
        arms_out.append({
            "label": a.get("label"),
            "kind": a.get("kind"),
            "treatment": a.get("treatment"),
            "outcome": a.get("outcome"),
            "adjust_set": list(a.get("adjust_set", []) or []),
            "values": a.get("values") or {},
            "condition_on": list((a.get("condition_on") or {}).keys()),
            "sweep_var": a.get("sweep_var"),
            "sweep_values": list(a.get("sweep_values", []) or []),
            "observed_vars": list(a.get("observed_vars") or []),
        })
    m = spec.get("measurement", {}) or {}
    c = spec.get("comparison", {}) or {}
    asrt = spec.get("assertion", {}) or {}
    return {
        "spec_id": spec.get("spec_id"),
        "arms": arms_out,
        "measurement": {
            "kind": m.get("kind"),
            "target": m.get("target"),
            "lhs": m.get("lhs"),
            "rhs": m.get("rhs"),
            "treatment": m.get("treatment"),
            "outcome": m.get("outcome"),
            "cond_set": list(m.get("cond_set", []) or []),
            "candidate_causes": list(m.get("candidate_causes", []) or []),
            "candidate_adjust_set": list(m.get("candidate_adjust_set", []) or []),
        },
        "comparison": {
            "kind": c.get("kind"),
            "ref_arm": c.get("ref_arm"),
            "order": list(c.get("order", []) or []),
        },
        "assertion": {
            "kind": asrt.get("kind"),
            "threshold": asrt.get("threshold"),
            "order": list(asrt.get("order", []) or []),
        },
    }


def _build_user_msg(
    entry: dict[str, Any],
    specs_key: str = "compiler_specs",
) -> str:
    """Build USER message body for a single baseline entry."""
    world_name = entry.get("world") or ""
    glossary = WORLD_GLOSSARIES.get(world_name, {})
    payload = {
        "entry_id": entry.get("id"),
        "fact_id": entry.get("fact_id"),
        "world": world_name,
        "world_description": glossary.get("description"),
        "world_variables": glossary.get("variables"),
        "world_edges": glossary.get("edges"),
        "category": entry.get("category"),
        "difficulty": entry.get("difficulty"),
        "claim": entry.get("claim"),
        "truth_value": entry.get("truth_value"),
        "specs": [_format_spec(s) for s in (entry.get(specs_key) or [])],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = _JSON_FENCE_RE.search(text)
    candidate = m.group(1) if m else None
    if candidate is None:
        m2 = _JSON_OBJ_RE.search(text)
        candidate = m2.group(0) if m2 else None
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _normalize_verdict(obj: dict[str, Any]) -> dict[str, Any]:
    out = {
        "verdict": str(obj.get("verdict", "abstain")).lower().replace("-", "_"),
        "violations": [],
        "confidence": float(obj.get("confidence", 0.0) or 0.0),
    }
    for v in obj.get("violations") or []:
        if not isinstance(v, dict):
            continue
        out["violations"].append({
            "category": str(v.get("category", "abstain")).lower().replace("-", "_"),
            "reason": str(v.get("reason", ""))[:500],
            "evidence": v.get("evidence") or {},
        })
    return out


def judge_entry(
    client: OpenAIClient,
    entry: dict[str, Any],
    model: str | None,
    specs_key: str = "compiler_specs",
    max_retries: int = 2,
) -> dict[str, Any]:
    user_body = _build_user_msg(entry, specs_key=specs_key)
    messages = [
        Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
        Message(role=MessageRole.USER, content=user_body),
    ]
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat(messages=messages, model=model, max_tokens=1200)
            raw = resp.message.content or ""
            parsed = _extract_json(raw)
            if parsed is None:
                last_err = f"attempt {attempt}: no JSON found"
                continue
            return {"ok": True, "result": _normalize_verdict(parsed), "raw": raw}
        except Exception as e:
            last_err = f"attempt {attempt}: {e!r}"
            continue
    return {"ok": False, "error": last_err, "result": None}


def _audit_batch(
    client: OpenAIClient,
    entries: list[dict[str, Any]],
    model: str | None,
    specs_key: str,
    workers: int,
    label: str,
) -> list[dict[str, Any]]:
    """Run pass-1 + auto pass-2 for a set of entries; return per-entry results."""
    def _run(idx_entry: tuple[int, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        idx, e = idx_entry
        r = judge_entry(client, e, model, specs_key=specs_key)
        return idx, r

    print(f"[{label}] Pass 1 on {len(entries)} entries...")
    results_by_idx: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_run, (i, e)) for i, e in enumerate(entries)]
        for fut in as_completed(futures):
            idx, r = fut.result()
            results_by_idx[idx] = r
            done = len(results_by_idx)
            if done % 5 == 0 or done == len(entries):
                print(f"  [{label}] pass 1: {done}/{len(entries)}")

    first_pass = []
    for i, entry in enumerate(entries):
        r = results_by_idx.get(i) or {"ok": False, "error": "missing"}
        first_pass.append({
            "entry_id": entry.get("id"),
            "fact_id": entry.get("fact_id"),
            "world": entry.get("world"),
            "category": entry.get("category"),
            "difficulty": entry.get("difficulty"),
            "claim": (entry.get("claim") or "")[:200],
            "compiler_compiled": entry.get("compiler_compiled"),
            "compiler_abstain_reason": entry.get("compiler_abstain_reason"),
            "gold_status": entry.get("gold_status"),
            "truth_value": entry.get("truth_value"),
            "pass_1": r,
        })

    # Pass 2 criteria: low confidence OR severe verdict OR error
    second_pass_idx = []
    for i, item in enumerate(first_pass):
        r1 = item["pass_1"]
        if not r1.get("ok") or not r1.get("result"):
            second_pass_idx.append(i)
            continue
        res = r1["result"]
        v = res["verdict"]
        conf = res.get("confidence", 0.0)
        if conf < LOW_CONFIDENCE_THRESHOLD or v in SEVERE_VERDICTS or any(
            viol["category"] in SEVERE_VERDICTS for viol in res.get("violations", [])
        ):
            second_pass_idx.append(i)

    if second_pass_idx:
        print(f"[{label}] Pass 2 on {len(second_pass_idx)} entries (low-conf or severe)...")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_run, (i, entries[i])): i for i in second_pass_idx
            }
            done = 0
            for fut in as_completed(futures):
                idx, r = fut.result()
                first_pass[idx]["pass_2"] = r
                done += 1
                if done % 5 == 0 or done == len(second_pass_idx):
                    print(f"  [{label}] pass 2: {done}/{len(second_pass_idx)}")

    return first_pass


def _summarize(per_entry: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter
    verdict_counts = Counter()
    per_world: dict[str, Counter] = {}
    per_category: dict[str, Counter] = {}
    violations_by_cat = Counter()
    severity_flags = 0
    abstained = 0
    errors = 0

    for item in per_entry:
        world = item.get("world") or "unknown"
        category = item.get("category") or "unknown"
        r = item.get("pass_2") or item["pass_1"]
        per_world.setdefault(world, Counter())
        per_category.setdefault(category, Counter())
        if not r.get("ok") or not r.get("result"):
            verdict_counts["error"] += 1
            per_world[world]["error"] += 1
            per_category[category]["error"] += 1
            errors += 1
            continue
        res = r["result"]
        v = res["verdict"]
        verdict_counts[v] += 1
        per_world[world][v] += 1
        per_category[category][v] += 1
        for viol in res.get("violations", []):
            violations_by_cat[viol["category"]] += 1
            if viol["category"] in SEVERE_VERDICTS:
                severity_flags += 1
        if v == "abstain":
            abstained += 1

    return {
        "total": len(per_entry),
        "verdict_distribution": dict(verdict_counts),
        "violation_category_counts": dict(violations_by_cat),
        "severe_verdicts": severity_flags,
        "abstained": abstained,
        "errors": errors,
        "per_world": {w: dict(c) for w, c in sorted(per_world.items())},
        "per_category": {cat: dict(c) for cat, c in sorted(per_category.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        default="research/synthesis/compiler_baseline_full_dump_v2.json",
        help="Path to compiler baseline dump",
    )
    parser.add_argument(
        "--out",
        default="./claim_compiler_coherence_audit.json",
        help="Output JSON path",
    )
    parser.add_argument("--model", default=None, help="Override AZURE_MODEL")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=None, help="Limit entries for testing")
    parser.add_argument(
        "--include-gold",
        action="store_true",
        help="Also audit gold_specs as a sanity control (should be ~100%% coherent)",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline).resolve()
    out_path = Path(args.out).resolve()

    with baseline_path.open(encoding="utf-8") as f:
        entries: list[dict[str, Any]] = json.load(f)
    if args.limit:
        entries = entries[: args.limit]
    print(f"Loaded {len(entries)} entries from {baseline_path}")

    client = OpenAIClient(model=args.model)
    model_name = args.model or client.default_model
    print(f"Using model: {model_name}")

    t0 = time.time()

    # Audit compiler_specs
    compiler_results = _audit_batch(
        client, entries, args.model, "compiler_specs", args.workers, "COMPILER"
    )

    # Optional: audit gold_specs
    gold_results = None
    if args.include_gold:
        gold_entries = [e for e in entries if (e.get("gold_specs") or [])]
        print(f"\n[GOLD] {len(gold_entries)} entries have gold_specs (control audit)")
        gold_results = _audit_batch(
            client, gold_entries, args.model, "gold_specs", args.workers, "GOLD"
        )

    duration = round(time.time() - t0, 1)

    out_obj: dict[str, Any] = {
        "meta": {
            "baseline_path": str(baseline_path),
            "total_entries": len(entries),
            "model": model_name,
            "duration_sec": duration,
            "include_gold": bool(args.include_gold),
        },
        "compiler_specs_audit": {
            "aggregate": _summarize(compiler_results),
            "per_entry": compiler_results,
        },
    }
    if gold_results is not None:
        out_obj["gold_specs_audit"] = {
            "aggregate": _summarize(gold_results),
            "per_entry": gold_results,
        }

    out_path.write_text(
        json.dumps(out_obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDone in {duration}s")
    print(f"Wrote: {out_path}")

    agg = out_obj["compiler_specs_audit"]["aggregate"]
    print("\n=== COMPILER_SPECS audit ===")
    print(f"Verdict distribution (total {agg['total']}):")
    for v, n in sorted(agg["verdict_distribution"].items(), key=lambda x: -x[1]):
        print(f"  {v:20s}  {n}")
    if agg["violation_category_counts"]:
        print(f"\nViolation category counts:")
        for cat, n in sorted(agg["violation_category_counts"].items(), key=lambda x: -x[1]):
            print(f"  {cat:20s}  {n}")
    print(f"\nPer-world verdicts:")
    for w, c in agg["per_world"].items():
        total_w = sum(c.values())
        coh = c.get("coherent", 0)
        print(f"  {w:40s}  coherent={coh}/{total_w}  {dict(c)}")

    if gold_results is not None:
        gagg = out_obj["gold_specs_audit"]["aggregate"]
        print("\n=== GOLD_SPECS audit (sanity control) ===")
        print(f"Verdict distribution (total {gagg['total']}):")
        for v, n in sorted(gagg["verdict_distribution"].items(), key=lambda x: -x[1]):
            print(f"  {v:20s}  {n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
