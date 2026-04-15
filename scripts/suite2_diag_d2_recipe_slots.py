"""Suite 2 diagnostic D2 — structured recipe elicitation.

Pregunta: si el LLM reconoce el patrón (D1), ¿sabe también completar los
SLOTS concretos de la receta correcta? Simplificamos el output a un JSON
pequeño y cerrado, y hacemos MATCH DETERMINISTA contra el gold
`StructuralContract`.

5 slots por claim (del átomo primario):
  1. arm_kinds  (set of {intervene, observe, adjust, sweep, baseline, condition})
  2. role_vars  (dict role->variable: treatment, outcome, mediator, modifier, condition_on)
  3. measurement_kind
  4. comparison_kind
  5. assertion_polarity

Plus: n_atoms + abstain handling.

Interpretación (por Codex 2026-04-15):
- slot_pass_rate ≥ 0.70 en todos los slots: el LLM "sabe la receta" — la
  falla del compiler real está en plumbing/schema/prompt, no en knowledge.
- slot_pass_rate < 0.50 en ≥ 2 slots: el LLM no tiene la receta estable —
  recognition-to-composition bridge está roto.
- mixto: per-slot y per-family breakdown muestran dónde apalancar
  exemplars.

Output: research/synthesis/suite2_diag_d2_results.json

Usage:
    conda activate sreg
    python scripts/suite2_diag_d2_recipe_slots.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from sreg.inference.openai_client import OpenAIClient
from sreg.inference.protocol import Message, MessageRole

from tests.eval.suite2_translation.fact_tables import ALL_FACTS
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS
from tests.eval.suite2_translation.worlds import ALL_WORLDS


def world_variable_list(world_key: str) -> list[str]:
    w = ALL_WORLDS.get(world_key)
    if w is None:
        return []
    return [v.name if hasattr(v, "name") else str(v) for v in w.variables]

# Allowed vocabularies (must match enum values in open_investigation.py)
ARM_KINDS = {"baseline", "intervene", "observe", "condition", "adjust", "sweep"}
MEASUREMENT_KINDS = {
    "mean", "variance", "quantile", "tail_prob", "prob",
    "correlation", "partial_correlation", "distribution", "identifiability_check",
}
COMPARISON_KINDS = {
    "identity", "difference", "ratio", "ranking", "gap",
    "proportion", "piecewise_fit", "contrast_diff",
}
ASSERTION_KINDS = {
    "positive", "negative", "near_zero", "greater_than", "less_than",
    "rank_order", "changepoint_exists", "sign_flip", "gap_material",
    "identifiable", "not_identifiable", "distinguishable", "not_distinguishable",
}

SYSTEM_PROMPT = f"""You are a recipe extractor for causal-inference claims.

Given a claim about a world, identify the MINIMAL RECIPE needed to verify
it against a Structural Causal Model (SCM). Output STRICT JSON with exactly
these fields — no prose, no code fences.

For expressible claims (status="compile"):
{{
  "status": "compile",
  "n_atoms": <int, usually 1, up to 3 for mediation/heterogeneity>,
  "primary_atom": {{
    "arm_kinds": [one or more of {sorted(ARM_KINDS)}],
    "role_vars": {{
      "treatment":    "<variable>" | null,
      "outcome":      "<variable>" | null,
      "mediator":     "<variable>" | null,
      "modifier":     "<variable>" | null,
      "condition_on": ["<var1>", "<var2>"]
    }},
    "measurement_kind": one of {sorted(MEASUREMENT_KINDS)},
    "comparison_kind":  one of {sorted(COMPARISON_KINDS)},
    "assertion_polarity": one of {sorted(ASSERTION_KINDS)}
  }}
}}

For non-expressible claims (status="abstain"):
{{
  "status": "abstain",
  "abstain_reason": "<short code like 'non_expressible' | 'latent' | 'temporal'>"
}}

Recipe intuition (pick the SIMPLEST that fits):
- "T causes Y" (positive effect)  -> arm_kinds=[intervene], treatment=T,
  outcome=Y, measurement=mean, comparison=difference, assertion=positive.
- "T correlates with Y"           -> arm_kinds=[observe], measurement=correlation,
  comparison=identity, assertion=positive/negative.
- "Effect of T on Y adjusting Z"  -> arm_kinds=[intervene], condition_on=[Z],
  measurement=mean, comparison=difference, assertion=positive/negative.
- "Effect through M (mediation)"  -> n_atoms=2+, mediator=M.
- "Effect depends on X"           -> n_atoms=2+, modifier=X.
- "Ranking X vs Y vs Z"           -> comparison=ranking, assertion=rank_order.
- "Variance of Y"                 -> measurement=variance.
- "Probability Y > c"             -> measurement=tail_prob or prob.

Rules:
- Use REAL variable names from the claim (T, Y, Z, M, X1, ...).
- role_vars.condition_on is a list; [] if none.
- Output MUST parse as JSON. No markdown fences. No extra keys.
"""


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object from LLM output."""
    if not text:
        return None
    # Strip markdown fences just in case
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    # Find the first {...} block that parses
    depth = 0
    start = None
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start = None
                    continue
    return None


def gold_slots(g) -> dict:
    """Extract the 5 slot fields from a GoldTarget."""
    if g.status == "abstain":
        return {"status": "abstain", "abstain_reason_code": g.abstain_reason_code}
    sc = g.structural_contract
    if sc is None:
        return {"status": "compile", "missing_contract": True}
    return {
        "status": "compile",
        "n_atoms": sc.n_atoms if isinstance(sc.n_atoms, int) else list(sc.n_atoms),
        "arm_kinds": sorted(sc.allowed_arm_kinds),
        "role_vars": dict(sc.required_role_vars),
        "measurement_kind": sc.required_measurement_kind,
        "comparison_kind": sc.required_comparison_kind,
        "assertion_polarity": sc.required_assertion_polarity,
        "mediator": sc.required_mediator,
        "modifier": sc.required_modifier,
        "condition_vars": sorted(sc.required_condition_vars),
        "cond_set": list(sc.required_cond_set) if sc.required_cond_set else [],
    }


def n_atoms_match(gold_n, pred_n) -> bool:
    if gold_n is None or pred_n is None:
        return False
    if isinstance(gold_n, list) and len(gold_n) == 2:
        return gold_n[0] <= pred_n <= gold_n[1]
    return int(gold_n) == int(pred_n)


def normalize_arm_kinds(raw) -> set[str]:
    if not raw:
        return set()
    if isinstance(raw, str):
        raw = [raw]
    out = set()
    for x in raw:
        if not isinstance(x, str):
            continue
        tok = x.strip().lower()
        if tok in ARM_KINDS:
            out.add(tok)
    return out


def score_target(gold: dict, pred: dict) -> dict:
    """Return per-slot verdict and aggregate score."""
    verdict: dict = {
        "slots": {},
        "n_matched": 0,
        "n_total": 0,
    }

    # Abstain handling
    g_status = gold.get("status")
    p_status = (pred or {}).get("status") if isinstance(pred, dict) else None
    verdict["slots"]["status"] = {"gold": g_status, "pred": p_status, "match": g_status == p_status}
    verdict["n_total"] += 1
    if g_status == p_status:
        verdict["n_matched"] += 1

    if g_status == "abstain":
        verdict["overall"] = "abstain_case"
        return verdict

    if p_status != "compile":
        verdict["overall"] = "status_mismatch"
        # Still 0/5 on the remaining slots; record explicitly
        for slot in ("n_atoms", "arm_kinds", "role_vars", "measurement_kind", "comparison_kind", "assertion_polarity"):
            verdict["slots"][slot] = {"gold": gold.get(slot), "pred": None, "match": False}
            verdict["n_total"] += 1
        return verdict

    pa = (pred or {}).get("primary_atom") or {}
    g_n = gold.get("n_atoms")
    p_n = pred.get("n_atoms")
    verdict["slots"]["n_atoms"] = {"gold": g_n, "pred": p_n, "match": n_atoms_match(g_n, p_n)}
    verdict["n_total"] += 1
    if verdict["slots"]["n_atoms"]["match"]:
        verdict["n_matched"] += 1

    # arm_kinds (set equality)
    g_ak = set(gold.get("arm_kinds") or [])
    p_ak = normalize_arm_kinds(pa.get("arm_kinds"))
    ak_match = g_ak == p_ak
    verdict["slots"]["arm_kinds"] = {"gold": sorted(g_ak), "pred": sorted(p_ak), "match": ak_match}
    verdict["n_total"] += 1
    if ak_match:
        verdict["n_matched"] += 1

    # role_vars: treatment + outcome are the critical pair; others credited as "extra" but not required
    g_rv = gold.get("role_vars") or {}
    p_rv = pa.get("role_vars") or {}
    critical = [r for r in ("treatment", "outcome") if r in g_rv]
    crit_match = all((p_rv.get(r) == g_rv.get(r)) for r in critical)
    verdict["slots"]["role_vars"] = {
        "gold": g_rv,
        "pred": p_rv,
        "match": crit_match,
        "critical_roles": critical,
    }
    verdict["n_total"] += 1
    if crit_match:
        verdict["n_matched"] += 1

    # measurement_kind
    g_mk = gold.get("measurement_kind")
    p_mk = (pa.get("measurement_kind") or "").lower()
    mk_match = p_mk == g_mk
    verdict["slots"]["measurement_kind"] = {"gold": g_mk, "pred": p_mk or None, "match": mk_match}
    verdict["n_total"] += 1
    if mk_match:
        verdict["n_matched"] += 1

    # comparison_kind
    g_cmp = gold.get("comparison_kind")
    p_cmp = (pa.get("comparison_kind") or "").lower()
    cmp_match = p_cmp == g_cmp
    verdict["slots"]["comparison_kind"] = {"gold": g_cmp, "pred": p_cmp or None, "match": cmp_match}
    verdict["n_total"] += 1
    if cmp_match:
        verdict["n_matched"] += 1

    # assertion_polarity
    g_asr = gold.get("assertion_polarity")
    p_asr = (pa.get("assertion_polarity") or "").lower()
    asr_match = p_asr == g_asr
    verdict["slots"]["assertion_polarity"] = {"gold": g_asr, "pred": p_asr or None, "match": asr_match}
    verdict["n_total"] += 1
    if asr_match:
        verdict["n_matched"] += 1

    verdict["overall"] = "compile_case"
    return verdict


def main() -> None:
    client = OpenAIClient()
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    print(f"Using model: {model}")

    # Map: (fact_id, surface_form_index) -> GoldTarget
    gold_map: dict[tuple[str, int], object] = {}
    for g in ALL_GOLD_TARGETS:
        gold_map[(g.fact_id, g.surface_form_index)] = g

    targets: list[tuple[str, str, str, str, dict]] = []
    for fact in ALL_FACTS:
        for idx, sf in enumerate(fact.surface_forms):
            key = (fact.fact_id, idx)
            g = gold_map.get(key)
            if g is None:
                continue
            tid = f"{fact.fact_id}_s{idx}"
            gold = gold_slots(g)
            gold["primary_family"] = fact.families[0] if fact.families else "UNKNOWN"
            gold["world"] = fact.world
            targets.append((tid, fact.fact_id, sf.text, gold["primary_family"], gold))

    print(f"Processing {len(targets)} targets with gold contracts")
    print("=" * 70)

    results: list[dict] = []
    per_slot_matched: dict[str, int] = defaultdict(int)
    per_slot_total: dict[str, int] = defaultdict(int)
    per_family_n_matched: dict[str, int] = defaultdict(int)
    per_family_n_total: dict[str, int] = defaultdict(int)

    t0 = time.monotonic()
    for tid, fact_id, claim, family, gold in targets:
        world = gold.get("world")
        vars_list = world_variable_list(world) if world else []
        vars_str = ", ".join(vars_list) if vars_list else "(unknown)"
        user_msg = (
            f"World: {world}\n"
            f"Variables available in this world (use THESE symbols in role_vars): {vars_str}\n"
            f"\nClaim:\n{claim}"
        )
        msgs = [
            Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=MessageRole.USER, content=user_msg),
        ]
        try:
            resp = client.chat(messages=msgs, model=model, temperature=0.0, max_tokens=500)
            raw = (resp.message.content or "") if resp.message else ""
        except Exception as e:
            raw = f"[error] {e}"

        parsed = extract_json(raw) or {}
        verdict = score_target(gold, parsed)

        for slot, info in verdict["slots"].items():
            per_slot_total[slot] += 1
            if info.get("match"):
                per_slot_matched[slot] += 1

        per_family_n_total[family] += verdict["n_total"]
        per_family_n_matched[family] += verdict["n_matched"]

        tag = f"{verdict['n_matched']}/{verdict['n_total']}"
        print(f"[{tag}] {tid:15s} fam={family:6s} slots_wrong="
              f"{[k for k,v in verdict['slots'].items() if not v.get('match')]}")

        results.append({
            "id": tid,
            "fact_id": fact_id,
            "claim": claim,
            "family": family,
            "world": gold.get("world"),
            "gold": {k: v for k, v in gold.items() if k not in ("primary_family", "world")},
            "predicted": parsed,
            "verdict": verdict,
            "raw_response": raw.strip()[:500],
        })

    dt = time.monotonic() - t0

    # Aggregate
    per_slot_acc = {
        slot: {
            "matched": per_slot_matched[slot],
            "total": per_slot_total[slot],
            "acc": per_slot_matched[slot] / per_slot_total[slot] if per_slot_total[slot] else 0.0,
        }
        for slot in per_slot_total
    }
    per_family_acc = {
        fam: {
            "matched": per_family_n_matched[fam],
            "total": per_family_n_total[fam],
            "acc": per_family_n_matched[fam] / per_family_n_total[fam] if per_family_n_total[fam] else 0.0,
        }
        for fam in sorted(per_family_n_total.keys())
    }

    total_matched = sum(per_slot_matched.values())
    total_slots = sum(per_slot_total.values())
    overall_acc = total_matched / total_slots if total_slots else 0.0

    # Interpretation
    weak_slots = [s for s, v in per_slot_acc.items() if v["acc"] < 0.50]
    strong_slots = [s for s, v in per_slot_acc.items() if v["acc"] >= 0.70]
    if len(weak_slots) >= 2:
        interp = (
            f"Recipe knowledge WEAK. {len(weak_slots)} slot(s) below 50% "
            f"({', '.join(weak_slots)}). The recognition-to-composition bridge "
            "is broken — the LLM cannot reliably translate the recognized "
            "pattern into the correct SCM operation. Exemplars targeted at the "
            "weakest slots are the highest-leverage next step."
        )
    elif len(strong_slots) == len(per_slot_acc):
        interp = (
            f"Recipe knowledge STRONG. All slots ≥ 70% "
            f"(overall {overall_acc*100:.0f}%). The compiler's real failures "
            "are in plumbing/schema (API arguments, field naming, sweep_values "
            "formatting), not in recipe knowledge. Fix the compiler prompt/"
            "schema bridge instead of teaching the pattern."
        )
    else:
        interp = (
            f"Recipe knowledge MIXED (overall {overall_acc*100:.0f}%). "
            f"Weak: {weak_slots or 'none'}. Strong: {strong_slots}. "
            "Target exemplars at the weak slots per family."
        )

    summary = {
        "generated_by": "scripts/suite2_diag_d2_recipe_slots.py",
        "model": model,
        "n_targets": len(targets),
        "overall_slot_accuracy": overall_acc,
        "per_slot_accuracy": per_slot_acc,
        "per_family_accuracy": per_family_acc,
        "weak_slots_lt_50": weak_slots,
        "strong_slots_ge_70": strong_slots,
        "elapsed_seconds": round(dt, 1),
        "interpretation": interp,
        "results": results,
    }

    out_path = Path("research/synthesis/suite2_diag_d2_results.json")
    out_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    print()
    print("=" * 70)
    print("D2 Summary")
    print("=" * 70)
    print(f"Overall slot accuracy: {total_matched}/{total_slots} = {overall_acc*100:.1f}%")
    print(f"Elapsed: {dt:.1f}s")
    print()
    print("Per-slot accuracy:")
    for slot, v in sorted(per_slot_acc.items(), key=lambda x: x[1]["acc"]):
        print(f"  {slot:22s}  {v['matched']}/{v['total']}  ({v['acc']*100:.0f}%)")
    print()
    print("Interpretation:")
    print(f"  {interp}")
    print()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
