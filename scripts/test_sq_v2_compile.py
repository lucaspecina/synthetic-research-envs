#!/usr/bin/env python
"""Test SQ v2 compile step on diverse sub-questions.

Creates a simple world (no E2E needed), writes 5 diverse SQ text_glosses,
compiles each through the v2 compile step (LLM call), and reports results.

Usage:
    python scripts/test_sq_v2_compile.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()

from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.tools.oi_compiler import build_world_summary
from sreg.tools.oi_sq_compiler import compile_sq_to_specs
from sreg.tools.oi_verifier import verify_atom
from sreg.solver.scm_solver import SCMSolver
from sreg.models.open_investigation import SQTier

# ---------------------------------------------------------------------------
# 1. Build a small world (environmental epidemiology, ~8 nodes)
# ---------------------------------------------------------------------------

spec = SCMSpec(
    variables=[
        SCMVariableSpec(
            name="industrial_proximity",
            equation="uniform(0, 10)",
            unit="km", description="Distance to industrial zone",
        ),
        SCMVariableSpec(
            name="air_pollution",
            equation="8.0 - 0.6 * industrial_proximity + normal(0, 1.5)",
            unit="ug/m3", description="PM2.5 air pollution level",
        ),
        SCMVariableSpec(
            name="socioeconomic_status",
            equation="normal(50, 15)",
            unit="index", description="Composite SES index (0-100)",
        ),
        SCMVariableSpec(
            name="healthcare_access",
            equation="0.3 * socioeconomic_status + normal(10, 5)",
            unit="score", description="Healthcare access score",
        ),
        SCMVariableSpec(
            name="smoking_rate",
            equation="30 - 0.2 * socioeconomic_status + normal(0, 5)",
            unit="percent", description="Smoking prevalence",
        ),
        SCMVariableSpec(
            name="respiratory_illness",
            equation="0.4 * air_pollution + 0.3 * smoking_rate - 0.15 * healthcare_access + normal(0, 2)",
            unit="rate", description="Respiratory illness incidence per 1000",
        ),
        SCMVariableSpec(
            name="cardiovascular_risk",
            equation="0.25 * air_pollution + 0.35 * smoking_rate - 0.1 * healthcare_access + 0.1 * respiratory_illness + normal(0, 3)",
            unit="score", description="Cardiovascular risk score",
        ),
        SCMVariableSpec(
            name="life_expectancy",
            equation="80 - 0.15 * respiratory_illness - 0.2 * cardiovascular_risk + 0.05 * socioeconomic_status + normal(0, 2)",
            unit="years", description="Life expectancy estimate",
        ),
    ],
    edges=[
        ("industrial_proximity", "air_pollution"),
        ("socioeconomic_status", "healthcare_access"),
        ("socioeconomic_status", "smoking_rate"),
        ("air_pollution", "respiratory_illness"),
        ("smoking_rate", "respiratory_illness"),
        ("healthcare_access", "respiratory_illness"),
        ("air_pollution", "cardiovascular_risk"),
        ("smoking_rate", "cardiovascular_risk"),
        ("healthcare_access", "cardiovascular_risk"),
        ("respiratory_illness", "cardiovascular_risk"),
        ("respiratory_illness", "life_expectancy"),
        ("cardiovascular_risk", "life_expectancy"),
        ("socioeconomic_status", "life_expectancy"),
    ],
)

# ---------------------------------------------------------------------------
# 2. Diverse SQ text_glosses — one per investigation type
# ---------------------------------------------------------------------------

DIVERSE_SQS = [
    {
        "sq_id": "sq_causal",
        "text_gloss": "Does air pollution causally increase respiratory illness incidence?",
        "focus_variables": ("air_pollution", "respiratory_illness"),
        "tier": SQTier.HIGH,
        "type_label": "CAUSAL",
    },
    {
        "sq_id": "sq_epistemic",
        "text_gloss": "Is the association between air pollution and respiratory illness robust to adjustment for smoking rate and healthcare access?",
        "focus_variables": ("air_pollution", "respiratory_illness", "smoking_rate", "healthcare_access"),
        "tier": SQTier.HIGH,
        "type_label": "EPISTEMOLOGICO",
    },
    {
        "sq_id": "sq_descriptive",
        "text_gloss": "What dimensions of health outcomes (respiratory, cardiovascular, life expectancy) correlate most strongly with socioeconomic status?",
        "focus_variables": ("socioeconomic_status", "respiratory_illness", "cardiovascular_risk", "life_expectancy"),
        "tier": SQTier.MEDIUM,
        "type_label": "DESCRIPTIVO",
    },
    {
        "sq_id": "sq_confounding",
        "text_gloss": "Does socioeconomic status confound the observed relationship between air pollution and cardiovascular risk?",
        "focus_variables": ("socioeconomic_status", "air_pollution", "cardiovascular_risk"),
        "tier": SQTier.HIGH,
        "type_label": "CONFOUNDING",
    },
    {
        "sq_id": "sq_mediation",
        "text_gloss": "Does respiratory illness mediate the effect of air pollution on life expectancy, or does air pollution affect life expectancy only through cardiovascular risk?",
        "focus_variables": ("air_pollution", "respiratory_illness", "cardiovascular_risk", "life_expectancy"),
        "tier": SQTier.MEDIUM,
        "type_label": "MEDIACION",
    },
]

# ---------------------------------------------------------------------------
# 3. Build world + LLM + compile
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("SQ v2 Compile Step — Test con 5 SQs diversas")
    print("=" * 60)

    # Build world
    print("\n[1] Construyendo mundo (environmental epi, 8 nodos)...")
    gen = SCMWorldGenTool()
    world = gen.generate(spec, seed=42)
    print(f"    OK: {len(world.variables)} variables, {len(world.observable_variables)} observables")

    # Build summary
    summary = build_world_summary(world, target="respiratory_illness")
    print(f"    WorldSummary: {len(summary.variables)} variables con anchors")
    print(f"    Variables: {', '.join(summary.observable_names)}")

    # Build LLM
    print("\n[2] Conectando LLM...")
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    print(f"    Modelo: {model}")

    def llm_call(system: str, user: str) -> str:
        resp = client.responses.create(
            model=model,
            instructions=system,
            input=[{"role": "user", "content": user}],
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    # Compile each SQ
    print("\n[3] Compilando SQs...\n")
    results = []
    for sq_def in DIVERSE_SQS:
        label = sq_def["type_label"]
        print(f"--- {label}: {sq_def['text_gloss'][:80]}...")

        result = compile_sq_to_specs(
            sq_id=sq_def["sq_id"],
            text_gloss=sq_def["text_gloss"],
            focus_variables=sq_def["focus_variables"],
            tier=sq_def["tier"],
            summary=summary,
            llm_call=llm_call,
        )

        if result.success:
            sq = result.sq
            n_req = len(sq.required_specs)
            n_sup = len(sq.support_specs)
            meas_kinds = {vs.spec.measurement.kind.value for vs in sq.verification_specs}
            comp_kinds = {vs.spec.comparison.kind.value for vs in sq.verification_specs}
            assert_kinds = {vs.spec.assertion.kind.value for vs in sq.verification_specs}

            print(f"    OK: {len(sq.verification_specs)} specs ({n_req} required, {n_sup} support)")
            print(f"    Measurement kinds: {meas_kinds}")
            print(f"    Comparison kinds:  {comp_kinds}")
            print(f"    Assertion kinds:   {assert_kinds}")

            # Show each spec briefly
            for i, vs in enumerate(sq.verification_specs):
                s = vs.spec
                role_tag = "REQ" if vs.role == "required" else "SUP"
                m = s.measurement
                var_info = ""
                if m.target:
                    var_info = f"target={m.target}"
                elif m.lhs and m.rhs:
                    var_info = f"lhs={m.lhs}, rhs={m.rhs}"
                elif m.treatment and m.outcome:
                    var_info = f"treat={m.treatment}, out={m.outcome}"
                cond = f", cond={list(m.cond_set)}" if m.cond_set else ""
                print(f"      [{role_tag}] {m.kind.value}({var_info}{cond}) -> {s.comparison.kind.value} -> {s.assertion.kind.value}")

            results.append({"label": label, "success": True, "n_specs": len(sq.verification_specs),
                           "n_required": n_req, "measurement_kinds": meas_kinds, "sq": sq})
        else:
            print(f"    FAIL: {result.errors}")
            results.append({"label": label, "success": False, "errors": result.errors})

        if result.errors and result.success:
            print(f"    Warnings: {result.errors}")
        print()

    # ---------------------------------------------------------------------------
    # 4. Verify specs against the SCM
    # ---------------------------------------------------------------------------
    print("=" * 60)
    print("[4] Verificando specs contra el SCM...")
    print("=" * 60)

    solver = SCMSolver(world)
    total_verified = 0
    total_true = 0
    total_errors = 0

    for r in results:
        if not r["success"]:
            continue
        sq = r["sq"]
        label = r["label"]
        print(f"\n--- {label} ---")

        sq_true = 0
        sq_total = 0
        sq_errors = 0
        for vs in sq.verification_specs:
            role_tag = "REQ" if vs.role == "required" else "SUP"
            try:
                verdict = verify_atom(vs.spec, world, solver, seed=42)
                vs.verdict = verdict
                holds = verdict.solver_assertion_holds
                sq_total += 1
                if holds:
                    sq_true += 1
                status = "TRUE" if holds else "FALSE"
                gt = verdict.ground_truth
                if isinstance(gt, float):
                    gt = f"{gt:.4f}"
                print(f"  [{role_tag}] {vs.spec.spec_id}: {status} (ground_truth={gt})")
            except Exception as e:
                sq_errors += 1
                print(f"  [{role_tag}] {vs.spec.spec_id}: ERROR ({e})")

        total_verified += sq_total
        total_true += sq_true
        total_errors += sq_errors
        rate = sq_true / sq_total if sq_total > 0 else 0
        print(f"  -> {sq_true}/{sq_total} TRUE ({rate:.0%}){f', {sq_errors} errors' if sq_errors else ''}")

    # ---------------------------------------------------------------------------
    # 5. Summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    ok = sum(1 for r in results if r["success"])
    print(f"Compilados: {ok}/{len(results)}")

    if ok > 0:
        all_kinds = set()
        total_specs = 0
        for r in results:
            if r["success"]:
                all_kinds.update(r["measurement_kinds"])
                total_specs += r["n_specs"]
        print(f"Total specs: {total_specs}")
        print(f"Measurement kinds unicos (across all SQs): {len(all_kinds)} -> {all_kinds}")
        print(f"Promedio specs/SQ: {total_specs / ok:.1f}")

    print(f"\nVerificacion contra SCM:")
    print(f"  Verificados: {total_verified}, TRUE: {total_true}, FALSE: {total_verified - total_true}, Errors: {total_errors}")
    if total_verified > 0:
        truth_rate = total_true / total_verified
        print(f"  Truth rate: {truth_rate:.0%}")

    # Key metrics from spec
    if ok > 0:
        print(f"\nCriterios del spec:")
        print(f"  unique_measurement_kinds > 3? {'SI' if len(all_kinds) > 3 else 'NO'} ({len(all_kinds)})")
        print(f"  spec_validity > 90%? {'SI' if total_errors == 0 or total_errors / total_specs < 0.1 else 'NO'} ({total_errors} errors de {total_specs})")
        if total_verified > 0:
            print(f"  truth_rate: {truth_rate:.0%}")


if __name__ == "__main__":
    main()
