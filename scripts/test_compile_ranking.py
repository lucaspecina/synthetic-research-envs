"""Test: can the compiler handle a ranking/variable-importance question?"""
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from sreg.models.open_investigation import SQTier
from sreg.tools.oi_compiler import build_world_summary
from sreg.tools.oi_sq_compiler import compile_sq_to_specs, validate_compilation_alignment
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.world.scm import SCMWorld
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import verify_atom

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s", stream=sys.stderr)

# Build a simple LLM caller
client = OpenAI(
    base_url=__import__("os").environ["AZURE_FOUNDRY_BASE_URL"],
    api_key=__import__("os").environ["AZURE_INFERENCE_CREDENTIAL"],
)
model = __import__("os").environ.get("AZURE_MODEL", "gpt-4o")

def llm_call(system: str, user: str) -> str:
    resp = client.responses.create(model=model, instructions=system, input=user)
    parts = []
    for item in resp.output:
        if item.type == "message":
            for part in item.content:
                if hasattr(part, "text"):
                    parts.append(part.text)
    return "".join(parts)

# Use a hand-crafted world (same as test_sq_v2_compile.py style)
from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
spec = SCMSpec(
    world_id="ranking-test",
    variables=[
        SCMVariableSpec(name="geology", role="latent", unit="index", range=(0, 1),
                       equation="beta(2, 3)"),
        SCMVariableSpec(name="spacing", role="observable", unit="m", range=(100, 600),
                       equation="normal(350, 100)"),
        SCMVariableSpec(name="fluid_intensity", role="observable", unit="bbl/ft", range=(5, 50),
                       equation="normal(25, 8)"),
        SCMVariableSpec(name="pressure", role="observable", unit="MPa", range=(20, 80),
                       equation="30 + 0.8 * fluid_intensity + normal(0, 5)"),
        SCMVariableSpec(name="stress_transfer", role="observable", unit="index", range=(0, 1),
                       equation="max(0, min(1, 0.3 - 0.001 * spacing + 0.005 * pressure + 0.2 * geology + normal(0, 0.05)))"),
        SCMVariableSpec(name="sanding_risk", role="observable", unit="%", range=(0, 100),
                       equation="max(0, min(100, 10 + 40 * stress_transfer + 15 * geology - 0.02 * spacing + 0.3 * fluid_intensity + normal(0, 5)))"),
    ],
    edges=[
        ("geology", "stress_transfer"), ("geology", "sanding_risk"),
        ("spacing", "stress_transfer"), ("spacing", "sanding_risk"),
        ("fluid_intensity", "pressure"),
        ("pressure", "stress_transfer"),
        ("stress_transfer", "sanding_risk"),
        ("fluid_intensity", "sanding_risk"),
    ],
)

gen = SCMWorldGenTool()
world = gen.generate(spec, seed=42)
summary = build_world_summary(world, "sanding_risk")
solver = SCMSolver(world)

print(f"World: {len(world.variables)} variables: {world.variables}")

# The ranking question
test_sqs = [
    {
        "sq_id": "ranking",
        "text_gloss": "Which observable variables have the strongest causal influence on sanding risk? Rank them from most to least impactful.",
        "focus_variables": ("spacing", "fluid_intensity", "pressure", "stress_transfer"),
        "tier": "high",
    },
    {
        "sq_id": "descriptive",
        "text_gloss": "What is the correlation structure among spacing, fluid intensity, pressure, and sanding risk?",
        "focus_variables": ("spacing", "fluid_intensity", "pressure", "sanding_risk"),
        "tier": "medium",
    },
]

for sq_def in test_sqs:
    print(f"\n{'='*60}")
    print(f"SQ: {sq_def['text_gloss']}")
    print(f"{'='*60}")

    result = compile_sq_to_specs(
        sq_id=sq_def["sq_id"],
        text_gloss=sq_def["text_gloss"],
        focus_variables=tuple(sq_def["focus_variables"]),
        tier=SQTier(sq_def["tier"]),
        summary=summary,
        llm_call=llm_call,
    )

    if not result.success:
        print(f"FAILED: {result.errors}")
        continue

    sq = result.sq
    print(f"Compiled: {len(sq.verification_specs)} specs "
          f"({len(sq.required_specs)} required, {len(sq.support_specs)} support)")

    # Show specs
    for j, vs in enumerate(sq.verification_specs):
        s = vs.spec
        print(f"\n  spec[{j}] [{vs.role}]:")
        for arm in s.arms:
            vals = dict(arm.values) if arm.values else {}
            extra = f" values={vals}" if vals else ""
            print(f"    arm: {arm.kind} ({arm.label}){extra}")
        m = s.measurement
        minfo = f"kind={m.kind}"
        for f in ("target", "lhs", "rhs", "treatment", "outcome"):
            v = getattr(m, f, None)
            if v:
                minfo += f" {f}={v}"
        if m.cond_set:
            minfo += f" cond_set={m.cond_set}"
        print(f"    measurement: {minfo}")
        if s.assertion:
            print(f"    assertion: {s.assertion.kind}")

    # Alignment check
    issues = validate_compilation_alignment(sq)
    if issues:
        for issue in issues:
            print(f"\n  [{issue['severity'].upper()}] {issue['check']}: {issue['message']}")
    else:
        print(f"\n  Alignment: OK")

    # Verify against SCM
    print(f"\n  SCM verification:")
    for j, vs in enumerate(sq.verification_specs):
        try:
            verdict = verify_atom(vs.spec, world, solver)
            print(f"    spec[{j}]: holds={verdict.solver_assertion_holds} "
                  f"(gt={verdict.ground_truth})")
        except Exception as e:
            print(f"    spec[{j}]: CRASH - {e}")

print("\nDone.")
