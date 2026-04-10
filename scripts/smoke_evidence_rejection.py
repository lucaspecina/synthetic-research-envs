"""Smoke E2E for #25: evidence_basis rejection in submit_claims.

Exercises the REAL solver path (run_code -> load_artifact -> submit_claims)
without LLM. Deterministic, fast, no external dependencies.

Expected output: 4 PASS lines, 0 FAIL.
"""
from __future__ import annotations

import sys

import numpy as np

from sreg.models.open_investigation import ClaimCard, EvidenceRef
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_runner import OIEpisodeRunner
from sreg.world.scm import SCMWorld, VariableMeta


def _setup():
    """Create minimal world + problem + runner."""
    world = SCMWorld(
        id="smoke_world",
        graph={"A": [], "B": ["A"], "Y": ["A", "B"]},
        equations={
            "A": lambda p, rng: rng.normal(5, 2),
            "B": lambda p, rng: 0.5 * p["A"] + rng.normal(3, 1),
            "Y": lambda p, rng: 0.8 * p["A"] + 0.3 * p["B"] + rng.normal(0, 1),
        },
        variable_meta={
            "A": VariableMeta(description="Exposure", unit="mg/L"),
            "B": VariableMeta(description="Mediator", unit="idx"),
            "Y": VariableMeta(description="Outcome", unit="pts"),
        },
    )
    rng = np.random.default_rng(42)
    cols = ["A", "B", "Y"]
    data = [{c: float(rng.normal()) for c in cols} for _ in range(50)]
    asset = DataAsset(
        artifact_id="dataset_bg",
        name="background",
        description="Background dataset",
        format="tabular",
        data=data,
        columns=cols,
        num_rows=50,
    )
    problem = ResearchProblem(
        world_id="smoke_world",
        title="Smoke test",
        description="Evidence rejection smoke",
        domain="test",
        data_assets=[asset],
        available_actions=[],
        budget=10,
        research_question="Does A affect Y?",
        target_node="Y",
        target_states=["low", "high"],
    )
    return OIEpisodeRunner(problem, world, n_mc=1000)


def _claim(claim_id: str, artifact_id: str) -> ClaimCard:
    return ClaimCard(
        claim_id=claim_id,
        claim_text="A has a positive causal effect on Y",
        focus_variables=["A", "Y"],
        confidence=0.8,
        evidence_basis=[
            EvidenceRef(artifact_id=artifact_id, rationale="analysis"),
        ],
    )


def main():
    results = []

    # --- Test 1: load_artifact via run_code (real solver path) ----
    runner = _setup()
    r = runner.run_code('df = load_artifact("dataset_bg")')
    ok = r["ok"] and len(runner.trace.accesses) == 1
    results.append(("load_artifact via run_code", ok))

    # --- Test 2: submit with fabricated ref -> atomic rejection ----
    try:
        runner.submit_claims([_claim("c1", "python_exec")])
        results.append(("fabricated ref rejected", False))
    except ValueError as e:
        msg = str(e)
        ok = (
            "SUBMISSION REJECTED" in msg
            and not runner.is_submitted
            and runner.trace.claim_steps == {}
        )
        results.append(("fabricated ref rejected", ok))

    # --- Test 3: resubmit with corrected ref -> success ----
    score = runner.submit_claims([_claim("c1", "dataset_bg")])
    ok = runner.is_submitted and score is not None
    results.append(("corrected resubmit accepted", ok))

    # --- Test 4: mixed batch atomic rejection ----
    runner2 = _setup()
    runner2.run_code('df = load_artifact("dataset_bg")')
    try:
        runner2.submit_claims([
            _claim("c_ok", "dataset_bg"),
            _claim("c_bad", "hallucinated_id"),
        ])
        results.append(("mixed batch atomic rejection", False))
    except ValueError:
        ok = not runner2.is_submitted and runner2.trace.claim_steps == {}
        results.append(("mixed batch atomic rejection", ok))

    # --- Report ----
    print("=" * 60)
    print("Smoke E2E: #25 evidence_basis rejection")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {name}")
    print("=" * 60)
    if all_pass:
        print(f"Result: ALL {len(results)} checks passed.")
    else:
        n_fail = sum(1 for _, p in results if not p)
        print(f"Result: {n_fail}/{len(results)} FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
