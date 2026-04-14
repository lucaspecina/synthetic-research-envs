"""Dump what the compiler actually produced for verdict failures."""
import sys, os, json
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


def spec_to_dict(spec):
    """Extract key info from an AtomicSpec."""
    arms = []
    for a in spec.arms:
        arms.append({
            "label": a.label,
            "kind": a.kind.value,
            "values": {k: v for k, v in a.values.items()} if a.values else {},
            "condition_on": {k: v for k, v in a.condition_on.items()} if a.condition_on else {},
        })
    return {
        "spec_id": spec.spec_id,
        "arms": arms,
        "measurement": {
            "kind": spec.measurement.kind.value,
            "target": spec.measurement.target,
            "treatment": spec.measurement.treatment,
            "outcome": spec.measurement.outcome,
            "lhs": spec.measurement.lhs,
            "rhs": spec.measurement.rhs,
        },
        "comparison": {
            "kind": spec.comparison.kind.value,
            "ref_arm": spec.comparison.ref_arm,
        },
        "assertion": {
            "kind": spec.assertion.kind.value,
            "threshold": spec.assertion.threshold,
        },
    }


def gold_spec_to_dict(spec):
    """Same but for gold specs."""
    return spec_to_dict(spec)


results = []

for gt in ALL_GOLD_TARGETS:
    fact = FACT_BY_ID.get(gt.fact_id)
    if fact is None:
        continue
    if gt.status == "abstain":
        continue

    wk = WORLD_FOR_FACT[gt.fact_id]
    sf = fact.surface_forms[gt.surface_form_index]
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
        evidence_basis=[EvidenceRef(
            artifact_id="gold_eval",
            rationale="Gold standard evaluation for compiler testing",
        )],
    )

    cout = compile_claim(claim, summary, llm_call=llm_call)

    if not cout.compiled:
        continue

    # Check verdict
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

    if not s3_ok:
        entry = {
            "id": f"{gt.fact_id}_s{gt.surface_form_index}",
            "difficulty": sf.difficulty,
            "claim": sf.text,
            "truth_value": fact.truth_value.value,
            "compiler_specs": [spec_to_dict(s) for s in cout.specs],
            "gold_specs": [gold_spec_to_dict(s) for s in gt.atoms],
            "verdicts": [
                {"atom_id": v.atom_id, "holds": v.solver_assertion_holds,
                 "detail": str(v.detail)[:200] if v.detail else None}
                for v in verdicts
            ],
            "backend": cout.units[0].backend if cout.units else None,
        }
        results.append(entry)

# Write JSON
out_path = "research/synthesis/compiler_baseline_failures.json"
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"Dumped {len(results)} verdict failures to {out_path}")

# Also print compact summary for each
for r in results:
    print(f"\n{'='*60}")
    print(f"  {r['id']} ({r['difficulty']}) | truth={r['truth_value']}")
    print(f"  Claim: {r['claim'][:80]}")
    print(f"  Compiler produced {len(r['compiler_specs'])} spec(s):")
    for i, cs in enumerate(r["compiler_specs"]):
        arms_str = ", ".join(
            f"{a['label']}({a['kind']}:{a['values']})" for a in cs["arms"]
        )
        print(f"    spec[{i}]: {cs['spec_id']}")
        print(f"      arms: {arms_str}")
        print(f"      measure: {cs['measurement']['kind']}")
        print(f"      compare: {cs['comparison']['kind']} ref={cs['comparison']['ref_arm']}")
        print(f"      assert:  {cs['assertion']['kind']} thr={cs['assertion']['threshold']}")
    print(f"  Gold expected {len(r['gold_specs'])} spec(s):")
    for i, gs in enumerate(r["gold_specs"]):
        arms_str = ", ".join(
            f"{a['label']}({a['kind']}:{a['values']})" for a in gs["arms"]
        )
        print(f"    spec[{i}]: {gs['spec_id']}")
        print(f"      arms: {arms_str}")
        print(f"      measure: {gs['measurement']['kind']}")
        print(f"      compare: {gs['comparison']['kind']} ref={gs['comparison']['ref_arm']}")
        print(f"      assert:  {gs['assertion']['kind']} thr={gs['assertion']['threshold']}")
    print(f"  Verdicts: ", end="")
    for v in r["verdicts"]:
        print(f"{'HOLD' if v['holds'] else 'FAIL'}({v['spec_id'][:30]}) ", end="")
    print()
