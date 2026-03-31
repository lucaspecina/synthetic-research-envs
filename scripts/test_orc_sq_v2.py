"""Quick test: orchestrator SQ v2 generation + compile.

Only runs the orchestrator (no solver). Shows the generated SQs v2
with their compiled AtomicSpecs.
"""
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from sreg.orchestrator.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(message)s",
    stream=sys.stderr,
)

seed_file = sys.argv[1] if len(sys.argv) > 1 else "seeds/vaca_muerta.md"
seed_content = Path(seed_file).read_text(encoding="utf-8")

goal = (
    "Generate a synthetic research case INSPIRED by (but not replicating) "
    "the following research seed. "
    "Create a fictional setting in a SIMILAR domain.\n\n"
    f"--- RESEARCH SEED ---\n{seed_content}\n--- END SEED ---"
)

print(f"=== Seed: {seed_file} ===", flush=True)
print("Running orchestrator (OI mode)...", flush=True)

orc = Orchestrator(oi_mode=True)
result = orc.run(goal)

if not result.world:
    print("FAILED: no world generated")
    sys.exit(1)

print(f"\nWorld: {result.world.id} ({len(result.world.variables)} variables)")
print(f"Variables: {result.world.variables}")

# Show v2 SQs
if result.sub_questions_v2:
    print(f"\n=== SQs v2: {len(result.sub_questions_v2)} compiled ===")
    for sq in result.sub_questions_v2:
        print(f"\n--- {sq.sq_id} (tier={sq.tier.value}) ---")
        print(f"  text: {sq.text_gloss}")
        print(f"  focus: {sq.focus_variables}")
        print(f"  specs: {len(sq.verification_specs)} "
              f"({len(sq.required_specs)} required, {len(sq.support_specs)} support)")
        for j, vs in enumerate(sq.verification_specs):
            s = vs.spec
            print(f"    spec[{j}] [{vs.role}]:")
            for arm in s.arms:
                vals = dict(arm.values) if arm.values else {}
                cond = dict(arm.condition_on) if arm.condition_on else {}
                adj = list(arm.adjust_set) if arm.adjust_set else []
                extra = ""
                if vals:
                    extra += f" values={vals}"
                if cond:
                    extra += f" cond={cond}"
                if adj:
                    extra += f" adjust={adj}"
                print(f"      arm: {arm.kind} ({arm.label}){extra}")
            m = s.measurement
            minfo = f"kind={m.kind}"
            if m.target:
                minfo += f" target={m.target}"
            if m.lhs:
                minfo += f" lhs={m.lhs}"
            if m.rhs:
                minfo += f" rhs={m.rhs}"
            if m.treatment:
                minfo += f" treatment={m.treatment}"
            if m.outcome:
                minfo += f" outcome={m.outcome}"
            if m.cond_set:
                minfo += f" cond_set={m.cond_set}"
            print(f"      measurement: {minfo}")
            if s.comparison:
                print(f"      comparison: {s.comparison.model_dump_json()}")
            if s.assertion:
                print(f"      assertion: {s.assertion.kind}")
else:
    print("\nNo v2 SQs generated!")
    if result.sub_questions:
        print(f"(v1 shim SQs: {len(result.sub_questions)})")

# Semantic alignment validation
print("\n=== Semantic Alignment Check ===")
from sreg.tools.oi_sq_compiler import validate_compilation_alignment

alignment_ok = 0
alignment_warn = 0
alignment_err = 0
for sq in result.sub_questions_v2:
    issues = validate_compilation_alignment(sq)
    if not issues:
        print(f"  {sq.sq_id}: OK")
        alignment_ok += 1
    else:
        for issue in issues:
            sev = issue["severity"].upper()
            print(f"  {sq.sq_id} [{sev}] {issue['check']}: {issue['message']}")
            if issue["severity"] == "error":
                alignment_err += 1
            else:
                alignment_warn += 1

print(f"\nAlignment: {alignment_ok} OK, {alignment_warn} warnings, {alignment_err} errors")

# Verify specs against SCM
print("\n=== Verification against SCM ===")
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import verify_atom

solver = SCMSolver(result.world)

total_specs = 0
total_execute = 0
total_true = 0
total_false = 0
total_crash = 0

for sq in result.sub_questions_v2:
    print(f"\n--- {sq.sq_id}: {sq.text_gloss[:80]} ---")
    for j, vs in enumerate(sq.verification_specs):
        total_specs += 1
        try:
            verdict = verify_atom(vs.spec, result.world, solver)
            gt = verdict.ground_truth
            holds = verdict.solver_assertion_holds
            detail = verdict.detail
            effect = detail.get("effect_size", detail.get("value", "?"))
            print(f"  spec[{j}] [{vs.role}]: holds={holds} "
                  f"(ground_truth={gt}, effect={effect})")
            total_execute += 1
            if holds:
                total_true += 1
            else:
                total_false += 1
        except Exception as e:
            print(f"  spec[{j}] [{vs.role}]: CRASH - {e}")
            total_crash += 1

print(f"\nSCM results: {total_specs} specs, {total_execute} executed, "
      f"{total_true} TRUE, {total_false} FALSE, {total_crash} CRASH")

print("\nDone.")
