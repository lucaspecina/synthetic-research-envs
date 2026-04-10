"""Smoke test: LLM relevance judge on realistic claim x SQ pairs.

Loads a Vaca Muerta world, compiles SQs v2, grounds answer keys,
then runs the judge on simulated solver claims (realistic mix of
relevant, tangential, and irrelevant findings).

Usage:
    python scripts/smoke_relevance_judge.py
"""

from __future__ import annotations

import json
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("smoke_judge")

# ---------------------------------------------------------------------------
# 1. Load world from existing SRC
# ---------------------------------------------------------------------------

def load_world():
    """Build a Vaca Muerta-like world inline (avoids SRC parsing issues)."""
    from sreg.world.scm import EquationFn, SCMWorld, VariableMeta

    import numpy as np

    def eq_stress(parents, rng):
        return rng.normal(17, 4)

    def eq_spacing(parents, rng):
        return rng.normal(290, 70)

    def eq_age(parents, rng):
        return max(1, rng.gamma(3, 8))

    def eq_proppant(parents, rng):
        return rng.normal(1800, 350)

    def eq_fluid(parents, rng):
        return rng.normal(18, 4.5)

    def eq_pressure(parents, rng):
        s = parents["stress_barrier_strength"]
        p = parents["proppant_intensity"]
        f = parents["fluid_intensity"]
        sp = parents["pad_spacing"]
        return 520 + 3.2*s + 0.025*p + 2.1*f - 0.035*sp + rng.normal(0, 35)

    def eq_comm(parents, rng):
        ptp = parents["peak_treatment_pressure"]
        p = parents["proppant_intensity"]
        f = parents["fluid_intensity"]
        sp = parents["pad_spacing"]
        s = parents["stress_barrier_strength"]
        return max(0, min(100,
            18 + 0.06*(ptp - 550) + 0.012*p + 0.65*f
            - 0.09*sp - 0.55*s + rng.normal(0, 6)
        ))

    def eq_sanding(parents, rng):
        ci = parents["communication_intensity"]
        a = parents["parent_production_age"]
        s = parents["stress_barrier_strength"]
        sp = parents["pad_spacing"]
        f = parents["fluid_intensity"]
        logit = -5.6 + 0.055*ci + 0.022*a - 0.06*s - 0.0016*sp + 0.35*max(0, f - 22)
        return min(0.98, max(0.01, 1 / (1 + np.exp(-logit + rng.normal(0, 0.45)))))

    graph = {
        "stress_barrier_strength": [],
        "pad_spacing": [],
        "parent_production_age": [],
        "proppant_intensity": [],
        "fluid_intensity": [],
        "peak_treatment_pressure": [
            "stress_barrier_strength", "proppant_intensity",
            "fluid_intensity", "pad_spacing",
        ],
        "communication_intensity": [
            "peak_treatment_pressure", "proppant_intensity",
            "fluid_intensity", "pad_spacing", "stress_barrier_strength",
        ],
        "parent_sanding_risk": [
            "communication_intensity", "parent_production_age",
            "stress_barrier_strength", "pad_spacing", "fluid_intensity",
        ],
    }

    equations: dict[str, EquationFn] = {
        "stress_barrier_strength": eq_stress,
        "pad_spacing": eq_spacing,
        "parent_production_age": eq_age,
        "proppant_intensity": eq_proppant,
        "fluid_intensity": eq_fluid,
        "peak_treatment_pressure": eq_pressure,
        "communication_intensity": eq_comm,
        "parent_sanding_risk": eq_sanding,
    }

    meta = {
        name: VariableMeta(unit="", range=(0, 100), description=name)
        for name in graph
    }

    return SCMWorld(
        graph=graph,
        equations=equations,
        variable_meta=meta,
        id="vaca_muerta_smoke",
    )


# ---------------------------------------------------------------------------
# 2. Define SQs (hardcoded v2-style, matching the brief)
# ---------------------------------------------------------------------------

BRIEF_TEXT = (
    "Investigate the causal mechanisms behind frac-hit sanding in aging "
    "parent wells. Identify main causal drivers, estimate how spacing and "
    "pumping changes would affect sanding risk, assess whether hydraulic "
    "communication is the main pathway, and determine if there is an "
    "unobserved geomechanical susceptibility factor."
)

# These mirror what the orchestrator would generate
RAW_SQS = [
    {
        "sq_id": "sq_1",
        "text_gloss": "What is the average treatment effect of pad_spacing on parent_sanding_risk?",
        "focus_variables": ("pad_spacing", "parent_sanding_risk"),
        "tier": "high",
    },
    {
        "sq_id": "sq_2",
        "text_gloss": "Does communication_intensity mediate the effect of fluid_intensity on parent_sanding_risk?",
        "focus_variables": ("fluid_intensity", "communication_intensity", "parent_sanding_risk"),
        "tier": "high",
    },
    {
        "sq_id": "sq_3",
        "text_gloss": "Which variables have the strongest causal effect on parent_sanding_risk?",
        "focus_variables": ("parent_sanding_risk",),
        "tier": "medium",
    },
    {
        "sq_id": "sq_4",
        "text_gloss": "Is the effect of pad_spacing on parent_sanding_risk identifiable from observational data?",
        "focus_variables": ("pad_spacing", "parent_sanding_risk"),
        "tier": "low",
    },
]


# ---------------------------------------------------------------------------
# 3. Simulated solver claims (realistic mix)
# ---------------------------------------------------------------------------

CLAIMS = [
    # Directly relevant to SQ1
    {
        "claim_id": "c1",
        "claim_text": (
            "Increasing pad_spacing by 50m reduces parent_sanding_risk by "
            "approximately 0.04 probability units (do-calculus ATE estimate "
            "controlling for stress_barrier_strength and formation factors)."
        ),
        "specs_summary": [
            {"measurement_kind": "mean", "comparison_kind": "difference",
             "primary_vars": "pad_spacing, parent_sanding_risk"},
        ],
    },
    # Directly relevant to SQ2 (mediation)
    {
        "claim_id": "c2",
        "claim_text": (
            "Communication_intensity mediates approximately 60% of the total "
            "effect of fluid_intensity on parent_sanding_risk. The remaining "
            "40% operates through a direct pathway independent of hydraulic "
            "communication severity."
        ),
        "specs_summary": [
            {"measurement_kind": "mean", "comparison_kind": "proportion",
             "primary_vars": "fluid_intensity, communication_intensity, parent_sanding_risk"},
        ],
    },
    # Tangentially relevant to SQ3 (ranking) — talks about one variable
    {
        "claim_id": "c3",
        "claim_text": (
            "Stress_barrier_strength has a significant negative effect on "
            "parent_sanding_risk (beta = -0.06, p < 0.001). Higher stress "
            "barriers appear to be protective against sanding events."
        ),
        "specs_summary": [
            {"measurement_kind": "mean", "comparison_kind": "difference",
             "primary_vars": "stress_barrier_strength, parent_sanding_risk"},
        ],
    },
    # TRUE but IRRELEVANT — correct fact about the world, wrong question
    {
        "claim_id": "c4",
        "claim_text": (
            "True_vertical_depth and proppant_intensity are positively "
            "correlated (r = 0.12, p = 0.03). Deeper wells tend to receive "
            "slightly higher proppant loading."
        ),
        "specs_summary": [
            {"measurement_kind": "correlation", "comparison_kind": "identity",
             "primary_vars": "true_vertical_depth, proppant_intensity"},
        ],
    },
    # Completely irrelevant — about a variable not in any SQ focus
    {
        "claim_id": "c5",
        "claim_text": (
            "Well_deviation shows a normal distribution centered around "
            "84 degrees with low variance. Most wells in the dataset have "
            "similar inclination angles."
        ),
        "specs_summary": [
            {"measurement_kind": "mean", "comparison_kind": "identity",
             "primary_vars": "well_deviation"},
        ],
    },
]


# ---------------------------------------------------------------------------
# 4. Compile SQs, ground answer keys, run judge
# ---------------------------------------------------------------------------


def make_llm_call():
    """Create an LLM callable using the project's OpenAI client."""
    from sreg.inference.openai_client import OpenAIClient
    from sreg.inference.protocol import Message, MessageRole

    client = OpenAIClient()

    def llm_call(system: str, user: str) -> str:
        resp = client.chat(
            messages=[
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user),
            ],
            temperature=0.0,
            max_tokens=4000,
        )
        return resp.message.content or ""

    return llm_call


def compile_and_ground_sqs(world, llm_call):
    """Compile raw SQs to v2 specs and ground against SCM."""
    from sreg.solver.scm_solver import SCMSolver
    from sreg.tools.oi_compiler import build_world_summary
    from sreg.tools.oi_sq_compiler import (
        compile_sq_to_specs,
        ground_sq_answer_key,
        render_answer_key,
    )

    target = "parent_sanding_risk"
    summary = build_world_summary(world, target, n_mc=20000, seed=42)
    solver = SCMSolver(world)

    compiled_sqs = []
    for raw in RAW_SQS:
        logger.info("Compiling SQ: %s", raw["sq_id"])
        result = compile_sq_to_specs(
            sq_id=raw["sq_id"],
            text_gloss=raw["text_gloss"],
            focus_variables=raw["focus_variables"],
            tier=raw["tier"],
            summary=summary,
            llm_call=llm_call,
        )
        if result.sq is None:
            logger.warning("  FAILED: %s", result.errors)
            continue

        # Ground against SCM
        gr = ground_sq_answer_key(result.sq, world, solver, seed=42)
        if not gr.success:
            logger.warning("  GROUNDING FAILED: %s", gr.warnings)
            continue

        # Render answer keys
        answer_keys = []
        for vs in gr.sq.verification_specs:
            if vs.verdict:
                ak = render_answer_key(vs.verdict)
                ak["role"] = vs.role
                answer_keys.append(ak)

        compiled_sqs.append({
            "sq_id": raw["sq_id"],
            "text_gloss": raw["text_gloss"],
            "focus_variables": list(raw["focus_variables"]),
            "tier": raw["tier"],
            "answer_keys": answer_keys,
        })

        logger.info(
            "  OK: %d specs, %d answer keys",
            len(gr.sq.verification_specs),
            len(answer_keys),
        )
        for ak in answer_keys:
            logger.info("    %s: %s", ak["result_type"], ak["headline"])

    return compiled_sqs


def run_judge(compiled_sqs, llm_call):
    """Run the relevance judge on all claim x SQ pairs."""
    from sreg.tools.oi_relevance_judge import judge_all_claims

    logger.info("\n=== RUNNING RELEVANCE JUDGE ===\n")
    results = judge_all_claims(
        claims=CLAIMS,
        sqs=compiled_sqs,
        brief_text=BRIEF_TEXT,
        llm_call=llm_call,
    )

    # -- Display results matrix --
    logger.info("\n=== RELEVANCE MATRIX ===\n")

    # Group by claim
    by_claim: dict[str, list] = {}
    for r in results:
        by_claim.setdefault(r["claim_id"], []).append(r)

    for claim in CLAIMS:
        cid = claim["claim_id"]
        logger.info("Claim %s: %s", cid, claim["claim_text"][:80])
        for r in by_claim.get(cid, []):
            marker = (
                "***" if r["relevance"] >= 0.7
                else "**" if r["relevance"] >= 0.4
                else "*" if r["relevance"] >= 0.1
                else "."
            )
            logger.info(
                "  %s %s: rel=%.2f  %s",
                marker, r["sq_id"], r["relevance"], r["reasoning"][:100],
            )
        logger.info("")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("Building inline Vaca Muerta world ...")
    world = load_world()
    logger.info("World loaded: %d variables", len(list(world.graph.keys())))

    llm_call = make_llm_call()

    logger.info("\n=== COMPILING & GROUNDING SQs ===\n")
    compiled_sqs = compile_and_ground_sqs(world, llm_call)
    logger.info("\nCompiled %d SQs with answer keys", len(compiled_sqs))

    if not compiled_sqs:
        logger.error("No SQs compiled -- cannot run judge")
        return

    results = run_judge(compiled_sqs, llm_call)

    # Save results
    out_path = "results/smoke_relevance_judge.json"
    with open(out_path, "w") as f:
        json.dump({
            "brief": BRIEF_TEXT,
            "sqs": compiled_sqs,
            "claims": CLAIMS,
            "relevance_results": results,
        }, f, indent=2, default=str)
    logger.info("Results saved to %s", out_path)


if __name__ == "__main__":
    main()
