"""Suite 2 diagnostic D1 — pattern recognition isolation.

Pregunta: ¿el LLM clasifica bien el patrón cuando le pedimos SOLO eso,
sin compilar?

Para los 55 claims de Suite 2, pedimos al LLM elegir UNA familia (primary)
entre las 30 disponibles. Comparamos con fact.families[0].

- Accuracy ≥ 80%  -> recognition OK, el gap está en composition.
- Accuracy < 50%  -> recognition también falla; recognition primero.
- 50-80%         -> gap mixto, depende de qué familias fallan.

Output: research/synthesis/suite2_diag_d1_results.json

Usage:
    conda activate sreg
    python scripts/suite2_diag_d1_pattern_recognition.py
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

# Family catalog — from research/synthesis/eval_suite_translation.md
FAMILY_CATALOG: list[tuple[str, str]] = [
    # CC-A: Pattern recognition
    ("CC-A1", "Causal effect (ATE via intervention): 'T causes Y', 'T affects Y', 'effect of T on Y'"),
    ("CC-A2", "Observational association (correlation / partial correlation, no intervention semantics)"),
    ("CC-A3", "Mediation: direct and/or indirect effect through mediator M"),
    ("CC-A4", "Heterogeneity / effect modification: effect depends on subgroup or covariate"),
    ("CC-A5", "Confounding: need to distinguish crude vs adjusted effect"),
    ("CC-A6", "Effect ranking: which variable has the strongest effect on Y"),
    ("CC-A7", "Tail risk: probability of extreme outcome"),
    ("CC-A8", "Variance effect: effect on spread/variance, not on mean"),
    # CC-B: Role binding / variable grounding
    ("CC-B1", "Edge orientation: T->Y vs Y->T"),
    ("CC-B2", "Role disambiguation: same 3 vars, different roles (mediator / confounder / modifier)"),
    ("CC-B3", "Variable alias: synonym or partial name maps to world variable"),
    ("CC-B4", "Sign/direction extraction: positive, negative, near_zero, numeric cues"),
    ("CC-B5", "Quantitative commitments: 'doubles', 'large effect', 'top decile'"),
    # CC-C: Linguistic complexity
    ("CC-C1", "Paraphrases: 3 formulations -> same spec"),
    ("CC-C2", "Negation: 'no effect', 'does not increase'"),
    ("CC-C3", "Multi-unit / compound: 1 claim -> multiple specs"),
    ("CC-C4", "Scope / subgroup: 'among older patients'"),
    ("CC-C5", "Conditioning semantics: 'holding Z constant', 'controlling for Z'"),
    # CC-D: Decision boundaries
    ("CC-D1", "Causal vs observational: same variables, different regime"),
    ("CC-D2", "Mediation vs confounding: same 3 variables, different structure"),
    ("CC-D3", "Ranking vs multiple causal effects"),
    ("CC-D4", "Adjusting-for-Z causal vs observational partial correlation"),
    # CC-E: Abstention
    ("CC-E1", "Temporal claims: 'X precedes Y in time'"),
    ("CC-E2", "Latent / unmeasured variables"),
    ("CC-E3", "Non-expressible: methodological, distributional"),
    # SQ-A: Direct questions
    ("SQ-A1", "Direct causal question: 'Does X affect Y?'"),
    ("SQ-A2", "Observational / associative question: 'Is X associated with Y?'"),
    ("SQ-A3", "Identifiability question: 'Can we estimate the causal effect?'"),
    ("SQ-A4", "Compound question: 'Does X affect Y, and if so, through what pathway?'"),
    # SQ-B: Decision boundaries
    ("SQ-B1", "Causal-adjust vs observational-partial-correlation: 'after adjusting for Z'"),
    ("SQ-B2", "Effect question vs mechanism question"),
    ("SQ-B3", "Paraphrases: 3 formulations -> equivalent specs"),
    # SQ-C: Abstention
    ("SQ-C1", "Non-expressible: 'What's the optimal X?'"),
    ("SQ-C2", "Unobservable variable in the question"),
]
FAMILY_IDS = {fid for fid, _ in FAMILY_CATALOG}

SYSTEM_PROMPT = """You are a classifier for causal-inference claims and questions.

Given a natural-language claim or question, assign it to exactly ONE family
from the catalog. You must pick the family that best captures the PRIMARY
semantic pattern — not a coincidental keyword match.

Family catalog:
""" + "\n".join(f"  {fid}  —  {desc}" for fid, desc in FAMILY_CATALOG) + """

Rules:
- Respond with EXACTLY one family id in the format `<FAMILY>: <FAMILY-ID>`.
- Example: `FAMILY: CC-A3`
- No reasoning, no prose, no JSON. Just that single line.
- If the claim fits several families, pick the MOST SPECIFIC one.
- Claims asking "what happens if we do X" or "X causes Y" are CC-A1 unless
  they explicitly invoke mediation (CC-A3), heterogeneity (CC-A4), or
  confounding (CC-A5).
- Questions ending with '?' and about causal effect are SQ-A1 (not CC-A1).
"""


def extract_family(text: str) -> str | None:
    if not text:
        return None
    m = re.search(r"FAMILY\s*:\s*([A-Z]{2,3}-[A-Z]\d)", text, re.IGNORECASE)
    if m:
        candidate = m.group(1).upper()
        if candidate in FAMILY_IDS:
            return candidate
    # fallback: any family-id token
    for tok in re.findall(r"[A-Z]{2,3}-[A-Z]\d", text):
        if tok in FAMILY_IDS:
            return tok
    return None


def main() -> None:
    client = OpenAIClient()
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    print(f"Using model: {model}")

    # Build the 55-target list the same way scripts/suite2_full_dump_v2.py does:
    # only surface forms that have a GoldTarget entry.
    gold_keys = {(g.fact_id, g.surface_form_index) for g in ALL_GOLD_TARGETS}
    targets: list[tuple[str, str, str, str]] = []  # (id, fact_id, claim, gold_family)
    for fact in ALL_FACTS:
        gold_family = fact.families[0] if fact.families else "UNKNOWN"
        for idx, sf in enumerate(fact.surface_forms):
            if (fact.fact_id, idx) not in gold_keys:
                continue
            tid = f"{fact.fact_id}_s{idx}"
            targets.append((tid, fact.fact_id, sf.text, gold_family))

    print(f"Classifying {len(targets)} targets")
    print("=" * 70)

    results: list[dict] = []
    correct = 0
    total = 0
    per_family_correct: dict[str, int] = defaultdict(int)
    per_family_total: dict[str, int] = defaultdict(int)

    t0 = time.monotonic()
    for tid, fact_id, claim, gold in targets:
        msgs = [
            Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=MessageRole.USER, content=f"Claim:\n{claim}"),
        ]
        try:
            resp = client.chat(messages=msgs, model=model, temperature=0.0, max_tokens=50)
            raw = (resp.message.content or "") if resp.message else ""
        except Exception as e:
            raw = f"[error] {e}"
        predicted = extract_family(raw)
        is_correct = predicted == gold
        correct += int(is_correct)
        total += 1
        per_family_total[gold] += 1
        if is_correct:
            per_family_correct[gold] += 1
        tag = "OK " if is_correct else "MISS"
        print(f"[{tag}] {tid:15s} gold={gold:6s} pred={(predicted or '?'):6s} raw={raw.strip()[:50]!r}")
        results.append({
            "id": tid,
            "fact_id": fact_id,
            "claim": claim,
            "gold_family": gold,
            "predicted_family": predicted,
            "correct": is_correct,
            "raw_response": raw.strip()[:200],
        })

    dt = time.monotonic() - t0

    # Per-family accuracy
    per_family_acc = {
        fam: {
            "correct": per_family_correct.get(fam, 0),
            "total": per_family_total[fam],
            "acc": per_family_correct.get(fam, 0) / per_family_total[fam],
        }
        for fam in sorted(per_family_total.keys())
    }

    # Confusion on miss
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        if not r["correct"]:
            confusion[r["gold_family"]][r["predicted_family"] or "UNPARSED"] += 1

    overall_acc = correct / total if total else 0.0

    # Interpretation
    if overall_acc >= 0.80:
        interp = (
            f"Recognition OK ({overall_acc*100:.0f}%). The LLM identifies the "
            "primary pattern correctly. The baseline gap is therefore "
            "COMPOSITIONAL — the LLM cannot translate the recognized pattern "
            "into a correct AtomicSpec."
        )
    elif overall_acc < 0.50:
        interp = (
            f"Recognition WEAK ({overall_acc*100:.0f}%). The LLM does not "
            "reliably identify the primary pattern. Fix recognition BEFORE "
            "attacking composition — exemplars without a pattern-recognition "
            "preface will not stick."
        )
    else:
        interp = (
            f"Recognition MIXED ({overall_acc*100:.0f}%). Look at per-family "
            "accuracy: some families are recognized, others are not. Targeted "
            "recognition scaffolding is likely needed for the weak families."
        )

    summary = {
        "generated_by": "scripts/suite2_diag_d1_pattern_recognition.py",
        "model": model,
        "n_targets": total,
        "correct": correct,
        "overall_accuracy": overall_acc,
        "elapsed_seconds": round(dt, 1),
        "per_family_accuracy": per_family_acc,
        "miss_confusion": {gold: dict(d) for gold, d in confusion.items()},
        "interpretation": interp,
        "results": results,
    }

    out_path = Path("research/synthesis/suite2_diag_d1_results.json")
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print("=" * 70)
    print("D1 Summary")
    print("=" * 70)
    print(f"Overall accuracy: {correct}/{total} = {overall_acc*100:.1f}%")
    print(f"Elapsed: {dt:.1f}s")
    print()
    print("Per-family accuracy:")
    for fam, stats in sorted(per_family_acc.items(), key=lambda x: -x[1]["total"]):
        print(f"  {fam:6s}  {stats['correct']}/{stats['total']}  ({stats['acc']*100:.0f}%)")
    print()
    print("Interpretation:")
    print(f"  {interp}")
    print()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
