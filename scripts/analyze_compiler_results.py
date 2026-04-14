"""Analyze compiler test results in detail — categorize failures."""
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from sreg.inference.openai_client import OpenAIClient
from sreg.inference.protocol import Message, MessageRole
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_compiler import build_world_summary
from sreg.tools.oi_extraction import compile_claim
from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.tools.oi_verifier import verify_atom

from tests.eval.suite2_translation.fact_tables import ALL_FACTS, Verdict
from tests.eval.suite2_translation.gold_targets import ALL_GOLD_TARGETS
from tests.eval.suite2_translation.worlds import ALL_WORLDS

FACT_BY_ID = {f.fact_id: f for f in ALL_FACTS}
WORLD_FOR_FACT = {f.fact_id: f.world for f in ALL_FACTS}

categories = {
    "full_pass": [],
    "adjust_only_s2": [],
    "real_struct_err": [],
    "verdict_fail": [],
    "stage1_fail": [],
}


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


client = OpenAIClient()
llm_call = make_llm_call(client)

solver_cache = {}
summary_cache = {}


def get_solver(wk):
    if wk not in solver_cache:
        w = ALL_WORLDS[wk]
        solver_cache[wk] = (w, SCMSolver(w, n_mc=50_000))
    return solver_cache[wk]


def get_summary(wk, tgt):
    k = (wk, tgt)
    if k not in summary_cache:
        summary_cache[k] = build_world_summary(ALL_WORLDS[wk], tgt)
    return summary_cache[k]


def infer_target(gt, fact):
    if gt.structural_contract and gt.structural_contract.required_role_vars:
        rv = gt.structural_contract.required_role_vars
        if "outcome" in rv:
            return rv["outcome"]
        if "rhs" in rv:
            return rv["rhs"]
    wk = WORLD_FOR_FACT.get(fact.fact_id, "")
    if "w1" in wk:
        return "Y"
    elif "w2" in wk:
        return "D"
    elif "w3" in wk:
        return "H"
    return "Y"


total = 0
for gt in ALL_GOLD_TARGETS:
    fact = FACT_BY_ID.get(gt.fact_id)
    if fact is None:
        continue
    total += 1
    wk = WORLD_FOR_FACT[gt.fact_id]
    sf = fact.surface_forms[gt.surface_form_index]
    label = f"{gt.fact_id}_s{gt.surface_form_index} ({sf.difficulty})"
    claim_text = sf.text[:70]

    target = infer_target(gt, fact)
    summary = get_summary(wk, target)
    world, solver = get_solver(wk)

    focus = []
    if gt.structural_contract and gt.structural_contract.required_role_vars:
        focus = list(set(gt.structural_contract.required_role_vars.values()))
    if not focus:
        focus = ["Y"]
    claim = ClaimCard(
        claim_id=f"{gt.fact_id}_s{gt.surface_form_index}",
        claim_text=sf.text,
        focus_variables=focus,
        confidence=1.0,
        evidence_basis=[EvidenceRef(artifact_id="gold_eval", rationale="Gold standard evaluation for compiler testing")],
    )

    cout = compile_claim(claim, summary, llm_call=llm_call)

    # Stage 1
    if gt.status == "compile":
        s1_ok = cout.compiled
    else:
        s1_ok = not cout.compiled

    if not s1_ok:
        exp = gt.status
        got = "compiled" if cout.compiled else "abstain"
        categories["stage1_fail"].append(
            f"{label}: expected {exp}, got {got} | {claim_text}"
        )
        continue

    if gt.status == "abstain" or not cout.compiled:
        categories["full_pass"].append(f"{label}: correctly abstained | {claim_text}")
        continue

    # Stage 2 analysis
    sc = gt.structural_contract
    s2_errors = []
    only_adjust_issue = True

    if sc:
        specs = cout.specs
        if isinstance(sc.n_atoms, int) and len(specs) != sc.n_atoms:
            s2_errors.append(f"n_atoms: {sc.n_atoms} vs {len(specs)}")
            only_adjust_issue = False
        elif isinstance(sc.n_atoms, tuple):
            lo, hi = sc.n_atoms
            if not (lo <= len(specs) <= hi):
                s2_errors.append(f"n_atoms: {lo}-{hi} vs {len(specs)}")
                only_adjust_issue = False

        for i, spec in enumerate(specs):
            arm_kinds = {a.kind.value for a in spec.arms}
            if not arm_kinds.issubset(sc.allowed_arm_kinds):
                extra = arm_kinds - sc.allowed_arm_kinds
                if extra <= {"adjust"} and "intervene" in sc.allowed_arm_kinds:
                    s2_errors.append(f"[adjust-swap] spec[{i}]")
                elif extra <= {"condition"} and "intervene" in sc.allowed_arm_kinds:
                    s2_errors.append(f"[condition-swap] spec[{i}]")
                    only_adjust_issue = False
                else:
                    s2_errors.append(
                        f"arm_kinds: {arm_kinds} vs {sc.allowed_arm_kinds}"
                    )
                    only_adjust_issue = False

            if spec.measurement.kind.value != sc.required_measurement_kind:
                s2_errors.append(
                    f"measurement: {spec.measurement.kind.value} vs "
                    f"{sc.required_measurement_kind}"
                )
                only_adjust_issue = False
            if spec.comparison.kind.value != sc.required_comparison_kind:
                s2_errors.append(
                    f"comparison: {spec.comparison.kind.value} vs "
                    f"{sc.required_comparison_kind}"
                )
                only_adjust_issue = False
            if spec.assertion.kind.value != sc.required_assertion_polarity:
                s2_errors.append(
                    f"assertion: {spec.assertion.kind.value} vs "
                    f"{sc.required_assertion_polarity}"
                )
                only_adjust_issue = False

    # Stage 3
    verdicts = []
    for spec in cout.specs:
        result = verify_atom(spec, world, solver, n_mc=50_000, seed=42)
        verdicts.append(result)

    all_hold = all(v.solver_assertion_holds for v in verdicts)
    any_fail = any(not v.solver_assertion_holds for v in verdicts)

    if fact.truth_value == Verdict.TRUE:
        s3_ok = all_hold
    elif fact.truth_value == Verdict.FALSE:
        s3_ok = any_fail
    elif fact.truth_value == Verdict.NOT_IDENTIFIABLE:
        s3_ok = all_hold
    else:
        s3_ok = False

    # Categorize
    if not s2_errors and s3_ok:
        categories["full_pass"].append(f"{label} | {claim_text}")
    elif not s3_ok:
        detail = "; ".join(s2_errors) if s2_errors else "no struct errors"
        v_detail = ", ".join(
            f"{v.atom_id}={'HOLD' if v.solver_assertion_holds else 'FAIL'}"
            for v in verdicts
        )
        categories["verdict_fail"].append(
            f"{label}: [{detail}] verdict=[{v_detail}] | {claim_text}"
        )
    elif s2_errors and only_adjust_issue:
        categories["adjust_only_s2"].append(
            f"{label}: {'; '.join(s2_errors)} | {claim_text}"
        )
    else:
        categories["real_struct_err"].append(
            f"{label}: {'; '.join(s2_errors)} | {claim_text}"
        )

print(f"\n{'='*70}")
print(f"  COMPILER ANALYSIS -- {total} gold targets")
print(f"{'='*70}")

for cat, items in categories.items():
    nice = {
        "full_pass": "FULL PASS (all 3 stages correct)",
        "adjust_only_s2": "ADJUST-SWAP ONLY (same result, different method)",
        "real_struct_err": "REAL STRUCTURAL ERROR (wrong structure, right answer)",
        "verdict_fail": "VERDICT WRONG (compiler got wrong answer)",
        "stage1_fail": "STAGE 1 FAIL (wrong compile/abstain decision)",
    }
    print(f"\n--- {nice[cat]} ({len(items)}) ---")
    for item in items:
        print(f"  {item}")

print(f"\n{'='*70}")
print(f"  SUMMARY")
print(f"{'='*70}")
fp = len(categories["full_pass"])
ao = len(categories["adjust_only_s2"])
rs = len(categories["real_struct_err"])
vf = len(categories["verdict_fail"])
s1 = len(categories["stage1_fail"])
print(f"  Full pass (3/3 stages):          {fp}")
print(f"  Adjust-swap only (harmless):     {ao}")
print(f"  Real structural error:           {rs}")
print(f"  Verdict wrong (answer wrong):    {vf}")
print(f"  Stage 1 fail (compile/abstain):  {s1}")
print(f"  Total:                           {total}")
effective = fp + ao
print(f"\n  Effective pass rate:             {effective}/{total} = {effective/total*100:.0f}%")
print(f"  (counting adjust-swap as pass since verdict is correct)")
real_errors = rs + vf + s1
print(f"  Real error rate:                 {real_errors}/{total} = {real_errors/total*100:.0f}%")
