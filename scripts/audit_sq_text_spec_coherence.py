"""SQ text<->specs semantic coherence audit (#42 fase 1 extension).

Per-SQ LLM judge: does the spec set semantically cover what the SQ text asks?
Input:
    canonical batch dir with N/src.json
Output:
    JSON with per-SQ verdict + per-case summary + aggregate.

Rubric (SQ may have multiple violations):
- coherent: specs measure what the text asks
- narrow: text broad, specs only cover a subset (missed dimension)
- incomplete: text has 2+ subclaims, spec set covers only some
- wrong_claim: spec measures a different thing than what text asks
- orphan_vars: vars in text absent from specs, or vice-versa
- contradictory: specs within same SQ contradict each other
- abstain: not enough info / unclear

Two-pass: re-audit SQs with confidence<0.6 or severe verdicts
(wrong_claim / contradictory / orphan_vars).
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


SYSTEM_PROMPT = """You are a semantic-coherence auditor for a scientific
evaluation system. For each sub-question (SQ) you receive:

1. The SQ text (natural language, scientific domain).
2. The SQ focus_variables (names from the underlying SCM).
3. A list of verification_specs derived from that SQ. Each spec has:
   - arms: list of query scenarios (kind, treatment, outcome, adjust_set, values)
   - measurement: what quantity to compute (kind, target, lhs/rhs, etc.)
   - comparison: how to compare measurements across arms (kind, ref_arm)
   - assertion: what should hold (kind: positive, negative, near_zero,
     distinguishable, identifiable, ...)

Your job: decide whether the spec set *semantically* covers what the SQ text
asks. Use this rubric (SQ can match multiple; lower severity first):

- coherent: specs measure what the text asks (no missing dimension).
- narrow: text is broad but specs cover only a subset (miss a dimension
  the text explicitly requests).
- incomplete: text has 2+ distinct subclaims; specs cover only some.
- wrong_claim: a spec measures a different thing than the text asks
  (e.g., text asks direction, spec asks distinguishability).
- orphan_vars: variables mentioned in the text are absent in specs, or
  specs involve vars not mentioned in text (check focus_variables glossary).
- contradictory: specs within the same SQ contradict each other
  (opposite assertions on the same claim, or incompatible measurements).
- abstain: not enough information to judge; the coupling is unclear.

HARD RULES:
- Every violation must cite evidence: spec_id + specific field
  (arm/measurement/comparison/assertion) + exact variable names.
- If evidence is weak, use `abstain` with low confidence. Do NOT invent.
- `coherent` means nothing extra is needed; only use when the set cleanly covers the text.

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
  text: "Does drug X reduce mortality compared to drug Y?"
  spec summary: arms=[intervene X=1, intervene Y=1], measurement=mean(mortality),
    comparison=difference, assertion=distinguishable
  verdict: wrong_claim (text asks for direction "reduce" but assertion is
    distinguishable which only tests "different"). cite assertion field on
    that spec_id.

EX2 (orphan_vars):
  text: "Does X cause Y controlling for Z?"
  focus_variables: ["X","Y","Z"]
  spec summary: arms=[kind=adjust, treatment=X, outcome=Y, adjust_set=[]],
    measurement=mean(Y), assertion=positive
  verdict: orphan_vars (Z mentioned in text but not used in any adjust_set).
    cite adjust_set field + variable Z.
"""


def _format_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Compact spec summary for LLM consumption (keep only semantic fields)."""
    arms_out = []
    for a in spec.get("arms", []):
        arms_out.append({
            "label": a.get("label"),
            "kind": a.get("kind"),
            "treatment": a.get("treatment"),
            "outcome": a.get("outcome"),
            "adjust_set": list(a.get("adjust_set", []) or []),
            "values": a.get("values") or {},
            "condition_on": list((a.get("condition_on") or {}).keys()),
            "sweep_var": a.get("sweep_var"),
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


def _build_user_msg(sq: dict[str, Any]) -> str:
    """Build USER message body for a single SQ."""
    payload = {
        "sq_id": sq.get("sq_id"),
        "tier": sq.get("tier"),
        "text": sq.get("text_gloss") or sq.get("text"),
        "focus_variables_glossary": sq.get("focus_variables") or [],
        "verification_specs": [
            {
                "role": vs.get("role"),
                **_format_spec(vs.get("spec") or {}),
            }
            for vs in sq.get("verification_specs", [])
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract first JSON object from text (strips fences, attempts outer)."""
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
    """Normalize verdict dict: lowercase labels, ensure required fields."""
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


def judge_sq(
    client: OpenAIClient,
    sq: dict[str, Any],
    model: str | None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Single LLM judgment call with JSON-parse retry."""
    user_body = _build_user_msg(sq)
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


def load_sqs(batch_dir: Path) -> list[dict[str, Any]]:
    """Load all SQs from all cases in batch dir."""
    out = []
    for case_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        src_path = case_dir / "src.json"
        if not src_path.exists():
            continue
        try:
            with src_path.open(encoding="utf-8") as f:
                src = json.load(f)
        except UnicodeDecodeError:
            with src_path.open(encoding="latin-1") as f:
                src = json.load(f)
        case_name = case_dir.name
        for sq in src.get("sub_questions_v2", []):
            out.append({"case": case_name, "sq": sq})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--batch",
        default="../../../results/p05_canonical_batch",
        help="Path to canonical batch dir containing N/src.json subdirs",
    )
    parser.add_argument(
        "--out",
        default="./sq_text_spec_coherence_audit.json",
        help="Output JSON path",
    )
    parser.add_argument("--model", default=None, help="Override AZURE_MODEL")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=None, help="Limit SQs for testing")
    parser.add_argument(
        "--no-second-pass",
        action="store_true",
        help="Skip re-audit of low-confidence / severe SQs",
    )
    args = parser.parse_args()

    batch_dir = Path(args.batch).resolve()
    out_path = Path(args.out).resolve()

    sqs = load_sqs(batch_dir)
    if args.limit:
        sqs = sqs[: args.limit]
    print(f"Loaded {len(sqs)} SQs from {batch_dir}")

    client = OpenAIClient(model=args.model)
    model_name = args.model or client.default_model
    print(f"Using model: {model_name}")

    t0 = time.time()

    def _run(idx_sq: tuple[int, dict[str, Any]]) -> tuple[int, dict[str, Any]]:
        idx, entry = idx_sq
        result = judge_sq(client, entry["sq"], args.model)
        return idx, result

    results_by_idx: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_run, (i, s)) for i, s in enumerate(sqs)]
        for fut in as_completed(futures):
            idx, r = fut.result()
            results_by_idx[idx] = r
            done = len(results_by_idx)
            if done % 5 == 0 or done == len(sqs):
                print(f"  pass 1: {done}/{len(sqs)}")

    # Assemble first-pass list
    first_pass = []
    for i, entry in enumerate(sqs):
        r = results_by_idx.get(i) or {"ok": False, "error": "missing"}
        first_pass.append({
            "case": entry["case"],
            "sq_id": entry["sq"].get("sq_id"),
            "tier": entry["sq"].get("tier"),
            "text": (entry["sq"].get("text_gloss") or "")[:200],
            "pass_1": r,
        })

    # Second pass: re-audit low-confidence or severe
    second_pass_needed = []
    if not args.no_second_pass:
        for i, item in enumerate(first_pass):
            r1 = item["pass_1"]
            if not r1.get("ok") or not r1.get("result"):
                second_pass_needed.append(i)
                continue
            res = r1["result"]
            v = res["verdict"]
            conf = res.get("confidence", 0.0)
            if conf < LOW_CONFIDENCE_THRESHOLD or v in SEVERE_VERDICTS or any(
                viol["category"] in SEVERE_VERDICTS for viol in res.get("violations", [])
            ):
                second_pass_needed.append(i)

        if second_pass_needed:
            print(f"Pass 2: re-auditing {len(second_pass_needed)} SQs "
                  f"(low-confidence or severe)")
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {
                    pool.submit(_run, (i, sqs[i])): i for i in second_pass_needed
                }
                done = 0
                for fut in as_completed(futures):
                    idx, r = fut.result()
                    first_pass[idx]["pass_2"] = r
                    done += 1
                    if done % 5 == 0 or done == len(second_pass_needed):
                        print(f"  pass 2: {done}/{len(second_pass_needed)}")

    # Aggregate
    from collections import Counter
    verdict_counts_final = Counter()
    per_case_counts: dict[str, Counter] = {}
    violations_by_category = Counter()
    severity_flags = 0
    abstained = 0
    errors = 0

    for item in first_pass:
        case = item["case"]
        r = item.get("pass_2") or item["pass_1"]
        per_case_counts.setdefault(case, Counter())
        if not r.get("ok") or not r.get("result"):
            verdict_counts_final["error"] += 1
            per_case_counts[case]["error"] += 1
            errors += 1
            continue
        res = r["result"]
        v = res["verdict"]
        verdict_counts_final[v] += 1
        per_case_counts[case][v] += 1
        for viol in res.get("violations", []):
            violations_by_category[viol["category"]] += 1
            if viol["category"] in SEVERE_VERDICTS:
                severity_flags += 1
        if v == "abstain":
            abstained += 1

    out_obj = {
        "aggregate": {
            "total_sqs": len(first_pass),
            "verdict_distribution": dict(verdict_counts_final),
            "violation_category_counts": dict(violations_by_category),
            "severe_verdicts": severity_flags,
            "abstained": abstained,
            "errors": errors,
            "model": model_name,
            "duration_sec": round(time.time() - t0, 1),
        },
        "per_case": {
            case: dict(cnt) for case, cnt in sorted(per_case_counts.items())
        },
        "per_sq": first_pass,
    }

    out_path.write_text(
        json.dumps(out_obj, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nDone in {out_obj['aggregate']['duration_sec']}s")
    print(f"Wrote: {out_path}")
    print(f"\nVerdict distribution:")
    for v, n in sorted(verdict_counts_final.items(), key=lambda x: -x[1]):
        print(f"  {v:20s}  {n}")
    if violations_by_category:
        print(f"\nViolation category counts (can be multiple per SQ):")
        for cat, n in sorted(violations_by_category.items(), key=lambda x: -x[1]):
            print(f"  {cat:20s}  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
