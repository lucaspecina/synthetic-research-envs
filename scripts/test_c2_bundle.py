#!/usr/bin/env python
"""Hand-craft C2 bundle specs and verify against e2e_03 world.

Tests whether the verifier can check "adjustment sensitivity":
- raw partial_correlation(particle, wheeze) with cond_set=()
- adjusted partial_correlation(particle, wheeze) with cond_set=[7 confounders]

If the raw correlation is positive and the adjusted is weaker,
C2's claim ("coefficient shrinks after adjusting") is verified.
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from sreg.models.open_investigation import (
    Assertion, AssertionKind,
    AtomicSpec,
    Comparison, ComparisonKind,
    Measurement, MeasurementKind,
    QueryArm, QueryKind,
)
from sreg.models.scm_spec import SCMSpec
from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_verifier import verify_atom
from sreg.tools.scm_world_gen import SCMWorldGenTool


def main():
    # Reconstruct world from e2e_03
    with open("experiments/e2e_03_epistemic/src.json") as f:
        src = json.load(f)

    scm_args = None
    for tc in src.get("process", {}).get("tools_called", []):
        if tc.get("tool") == "scm_construct":
            res = tc.get("result", {})
            if "world_id" in res or "error" not in res:
                scm_args = tc["args"]
                break
    if scm_args is None:
        for tc in src.get("process", {}).get("tools_called", []):
            if tc.get("tool") == "scm_construct":
                scm_args = tc["args"]
    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    world = gen.generate(spec, seed=42)
    solver = SCMSolver(world, n_mc=20_000)

    treatment = "particle_proxy_index"
    outcome = "childhood_wheeze_prevalence"
    confounders = (
        "traffic_density",
        "industrial_emission_intensity",
        "socioeconomic_strain",
        "green_space_coverage",
        "healthcare_access",
        "ambient_temperature",
        "wind_dispersion_index",
    )

    # --- Spec 1: Raw association (no conditioning) ---
    raw_spec = AtomicSpec(
        spec_id="c2_raw_assoc",
        arms=(
            QueryArm(label="baseline", kind=QueryKind.BASELINE),
        ),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs=treatment,
            rhs=outcome,
            cond_set=(),  # no conditioning = raw correlation
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )

    # --- Spec 2: Adjusted association (conditioning on 7 vars) ---
    adj_spec = AtomicSpec(
        spec_id="c2_adj_assoc",
        arms=(
            QueryArm(label="baseline", kind=QueryKind.BASELINE),
        ),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs=treatment,
            rhs=outcome,
            cond_set=confounders,
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.POSITIVE),
    )

    # --- Spec 3: Raw association is NEAR_ZERO check (should FAIL) ---
    raw_nearzero = AtomicSpec(
        spec_id="c2_raw_nearzero",
        arms=(
            QueryArm(label="baseline", kind=QueryKind.BASELINE),
        ),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs=treatment,
            rhs=outcome,
            cond_set=(),
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.NEAR_ZERO),
    )

    # --- Spec 4: Adjusted association is NEAR_ZERO (might be true if confounders explain) ---
    adj_nearzero = AtomicSpec(
        spec_id="c2_adj_nearzero",
        arms=(
            QueryArm(label="baseline", kind=QueryKind.BASELINE),
        ),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs=treatment,
            rhs=outcome,
            cond_set=confounders,
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.NEAR_ZERO),
    )

    specs = [
        ("C2 raw positive?", raw_spec),
        ("C2 adjusted positive?", adj_spec),
        ("C2 raw near_zero? (should fail)", raw_nearzero),
        ("C2 adjusted near_zero?", adj_nearzero),
    ]

    print("=== C2 BUNDLE DIAGNOSTIC ===\n")
    for desc, spec in specs:
        verdict = verify_atom(spec, world, solver, 20_000, 42)
        print(f"{desc}")
        print(f"  holds: {verdict.solver_assertion_holds}")
        print(f"  ground_truth: {verdict.ground_truth}")
        print(f"  detail: {verdict.detail}")
        print()

    # --- Also test C3: wind → particle direction ---
    print("=== C3 DIRECTION DIAGNOSTIC ===\n")

    wind_particle_neg = AtomicSpec(
        spec_id="c3_wind_particle_neg",
        arms=(QueryArm(label="baseline", kind=QueryKind.BASELINE),),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs="wind_dispersion_index",
            rhs="particle_proxy_index",
            cond_set=(),
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.NEGATIVE),
    )

    wind_particle_nz = AtomicSpec(
        spec_id="c3_wind_particle_nz",
        arms=(QueryArm(label="baseline", kind=QueryKind.BASELINE),),
        measurement=Measurement(
            kind=MeasurementKind.PARTIAL_CORRELATION,
            lhs="wind_dispersion_index",
            rhs="particle_proxy_index",
            cond_set=(),
        ),
        comparison=Comparison(kind=ComparisonKind.IDENTITY),
        assertion=Assertion(kind=AssertionKind.NEAR_ZERO),
    )

    for desc, s in [
        ("C3 wind->particle negative?", wind_particle_neg),
        ("C3 wind->particle near_zero?", wind_particle_nz),
    ]:
        verdict = verify_atom(s, world, solver, 20_000, 42)
        print(f"{desc}")
        print(f"  holds: {verdict.solver_assertion_holds}")
        print(f"  ground_truth: {verdict.ground_truth}")
        print(f"  detail: {verdict.detail}")
        print()


if __name__ == "__main__":
    main()
