"""Inspection script: full scoring pipeline trace as readable markdown.

Shows the complete flow from SQs -> SCM answer keys -> claims ->
relevance judge -> score, so a human can read every step.

Usage:
    # Re-run full pipeline (requires LLM):
    python scripts/inspect_pipeline.py

    # Generate report from existing data (no LLM calls):
    python scripts/inspect_pipeline.py --from-json results/smoke_relevance_judge.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap
from io import StringIO
from typing import Any

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("inspect")


# ---------------------------------------------------------------------------
# 1. Inline world (same as smoke test)
# ---------------------------------------------------------------------------

def load_world():
    """Build Vaca Muerta world inline."""
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
        "stress_barrier_strength": VariableMeta(
            unit="MPa", range=(5, 30),
            description="Geomechanical stress barrier between parent and child well"),
        "pad_spacing": VariableMeta(
            unit="m", range=(100, 500),
            description="Distance between parent and child well pads"),
        "parent_production_age": VariableMeta(
            unit="years", range=(1, 40),
            description="Years of production from parent well before child completion"),
        "proppant_intensity": VariableMeta(
            unit="kg/m", range=(800, 3000),
            description="Proppant loading per meter of lateral in child frac"),
        "fluid_intensity": VariableMeta(
            unit="bbl/m", range=(5, 35),
            description="Fluid volume per meter of lateral in child frac"),
        "peak_treatment_pressure": VariableMeta(
            unit="bar", range=(400, 800),
            description="Maximum pump pressure during child frac treatment"),
        "communication_intensity": VariableMeta(
            unit="%", range=(0, 100),
            description="Degree of hydraulic connection between parent and child"),
        "parent_sanding_risk": VariableMeta(
            unit="probability", range=(0, 1),
            description="Probability of sand production event in parent well"),
    }

    return SCMWorld(
        graph=graph,
        equations=equations,
        variable_meta=meta,
        id="vaca_muerta_inspect",
    )


# ---------------------------------------------------------------------------
# 2. SQs and claims (same as smoke test)
# ---------------------------------------------------------------------------

BRIEF_TEXT = (
    "Investigate the causal mechanisms behind frac-hit sanding in aging "
    "parent wells. Identify main causal drivers, estimate how spacing and "
    "pumping changes would affect sanding risk, assess whether hydraulic "
    "communication is the main pathway, and determine if there is an "
    "unobserved geomechanical susceptibility factor."
)

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

CLAIMS = [
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
# 3. LLM client
# ---------------------------------------------------------------------------

def make_llm_call():
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


# ---------------------------------------------------------------------------
# 4. Markdown report builder
# ---------------------------------------------------------------------------

class ReportBuilder:
    """Accumulates markdown sections."""

    def __init__(self):
        self._buf = StringIO()

    def h1(self, text: str):
        self._buf.write(f"\n# {text}\n\n")

    def h2(self, text: str):
        self._buf.write(f"\n## {text}\n\n")

    def h3(self, text: str):
        self._buf.write(f"\n### {text}\n\n")

    def p(self, text: str):
        self._buf.write(f"{text}\n\n")

    def bullet(self, text: str):
        self._buf.write(f"- {text}\n")

    def blank(self):
        self._buf.write("\n")

    def code(self, text: str, lang: str = ""):
        self._buf.write(f"```{lang}\n{text}\n```\n\n")

    def table(self, headers: list[str], rows: list[list[str]]):
        """Render a markdown table."""
        self._buf.write("| " + " | ".join(headers) + " |\n")
        self._buf.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
        for row in rows:
            self._buf.write("| " + " | ".join(str(c) for c in row) + " |\n")
        self._buf.write("\n")

    def get(self) -> str:
        return self._buf.getvalue()


# ---------------------------------------------------------------------------
# 5. Pipeline steps with report output
# ---------------------------------------------------------------------------

def step_world(report: ReportBuilder, world):
    """Document the world/DAG."""
    report.h1("Pipeline Inspection: Scoring de Open Investigation")
    report.p(
        "Este documento muestra el pipeline completo de scoring paso a paso, "
        "para que un humano pueda leer cada decision del sistema."
    )

    report.h2("1. Mundo (SCM World)")
    report.p(f"**World ID:** `{world.id}`")
    report.p(f"**Variables:** {len(list(world.graph.keys()))}")

    # world.graph is a dict {child: [parents]}, world._dag is the DiGraph
    rows = []
    for name, parents in world.graph.items():
        meta = world.variable_meta.get(name)
        unit = meta.unit if meta else ""
        desc = meta.description if meta else ""
        rows.append([
            f"`{name}`",
            unit,
            ", ".join(f"`{p}`" for p in parents) if parents else "(root)",
            desc[:60],
        ])
    report.table(["Variable", "Unit", "Parents (causas)", "Descripcion"], rows)

    report.p("**DAG visual (texto):**")
    dag_lines = []
    for child, parents in world.graph.items():
        for p in parents:
            dag_lines.append(f"  {p} --> {child}")
    report.code("\n".join(dag_lines))


def step_brief(report: ReportBuilder):
    """Document the research brief."""
    report.h2("2. Research Brief")
    report.p(
        "El brief es lo que el investigador (solver) recibe como pregunta "
        "de investigacion. Define QUE hay que investigar."
    )
    report.code(BRIEF_TEXT)


def step_sqs(report: ReportBuilder, compiled_sqs):
    """Document each SQ with its answer keys."""
    report.h2("3. Sub-Questions (SQs)")
    report.p(
        "Las SQs descomponen el brief en preguntas atomicas verificables. "
        "Cada una tiene un **tier** (prioridad) y **focus variables** "
        "(las variables que investiga)."
    )

    for sq in compiled_sqs:
        tier_emoji = {"high": "[HIGH]", "medium": "[MED]", "low": "[LOW]"}
        tier_tag = tier_emoji.get(sq["tier"], sq["tier"])

        report.h3(f"SQ: {sq['sq_id']} {tier_tag}")
        report.p(f"**Pregunta:** {sq['text_gloss']}")
        report.p(f"**Variables foco:** {', '.join(sq['focus_variables'])}")
        report.p(f"**Tier:** {sq['tier']}")

        if sq.get("answer_keys"):
            report.p("**Answer Keys (verdad del SCM):**")
            report.p(
                "Esto es lo que el mundo (SCM) dice que es VERDAD para esta "
                "sub-question. El solver no ve esto -- es la clave de respuestas."
            )
            for i, ak in enumerate(sq["answer_keys"]):
                role = ak.get("role", "?")
                rtype = ak.get("result_type", "?")
                headline = ak.get("headline", "?")
                meta = ak.get("meta", {})
                mk = meta.get("measurement_kind", "?")
                ck = meta.get("comparison_kind", "?")

                report.bullet(
                    f"**Spec {i+1}** [{role}]: `{rtype}` -- "
                    f"{headline}"
                )
                report.bullet(
                    f"  Tipo: measurement=`{mk}`, comparison=`{ck}`"
                )

                # Show arms (measurements per arm)
                arms = ak.get("arms", {})
                if arms:
                    arm_parts = []
                    for arm_name, arm_val in arms.items():
                        if isinstance(arm_val, dict):
                            # arm_val might be {variable: value}
                            for var, val in arm_val.items():
                                if isinstance(val, float):
                                    arm_parts.append(f"{arm_name}.{var}={val:.4g}")
                                else:
                                    arm_parts.append(f"{arm_name}.{var}={val}")
                        elif isinstance(arm_val, (int, float)):
                            arm_parts.append(f"{arm_name}={arm_val:.4g}")
                    if arm_parts:
                        report.bullet(f"  Mediciones: {', '.join(arm_parts)}")

                # Show value
                value = ak.get("value")
                if value is not None and rtype not in ("error", "empty"):
                    if isinstance(value, float):
                        report.bullet(f"  **Valor:** {value:.4g}")
                    elif isinstance(value, list):
                        report.bullet(f"  **Valor:** {' > '.join(str(v) for v in value)}")
                    else:
                        report.bullet(f"  **Valor:** {value}")

                # Show extra values (ranking/gap)
                extra_vals = ak.get("values")
                if extra_vals and isinstance(extra_vals, dict):
                    parts = [f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                             for k, v in extra_vals.items()]
                    report.bullet(f"  Valores detalle: {', '.join(parts)}")

            report.blank()
        else:
            report.p("*(Sin answer keys -- compilacion fallida)*")


def step_claims(report: ReportBuilder):
    """Document the claims."""
    report.h2("4. Claims del Solver")
    report.p(
        "Estos son los hallazgos que el solver (investigador) reporta. "
        "En un E2E real, el solver los genera despues de analizar los datos. "
        "Aqui usamos claims hardcodeados para inspeccionar el scoring."
    )

    for claim in CLAIMS:
        cid = claim["claim_id"]
        report.h3(f"Claim: {cid}")
        report.p(f"**Texto:** {claim['claim_text']}")
        if claim.get("specs_summary"):
            for cs in claim["specs_summary"]:
                report.bullet(
                    f"Estructura: measurement=`{cs.get('measurement_kind', '?')}`, "
                    f"comparison=`{cs.get('comparison_kind', '?')}`, "
                    f"vars=`{cs.get('primary_vars', '?')}`"
                )
            report.blank()

    report.p("**Expectativas:**")
    report.bullet("**c1** -- Directamente relevante a SQ1 (spacing -> sanding)")
    report.bullet("**c2** -- Directamente relevante a SQ2 (mediacion via communication)")
    report.bullet("**c3** -- Tangencialmente relevante a SQ3 (un driver, no ranking)")
    report.bullet("**c4** -- VERDADERO pero IRRELEVANTE (variables que no estan en ningun SQ)")
    report.bullet("**c5** -- Completamente irrelevante (variable no existe en el mundo)")
    report.blank()


def step_relevance(report: ReportBuilder, relevance_results, compiled_sqs):
    """Document the relevance judgments."""
    report.h2("5. Evaluacion de Relevancia (LLM Judge)")
    report.p(
        "Para cada par (claim x SQ), el LLM judge evalua si el claim "
        "es relevante para la sub-question. Score 0.0 a 1.0."
    )
    report.p(
        "**Pre-filtro:** si las variables del claim y del SQ no se solapan, "
        "se asigna relevancia=0.0 sin llamar al LLM."
    )

    # Build lookup
    sq_ids = [sq["sq_id"] for sq in compiled_sqs]
    by_claim: dict[str, list] = {}
    for r in relevance_results:
        by_claim.setdefault(r["claim_id"], []).append(r)

    # Summary table
    report.h3("Matriz de Relevancia")
    headers = ["Claim"] + sq_ids + ["Mejor match"]
    rows = []
    for claim in CLAIMS:
        cid = claim["claim_id"]
        results_for_claim = by_claim.get(cid, [])
        row = [f"**{cid}**"]
        best_score = 0.0
        best_sq = "-"
        for sq_id in sq_ids:
            match = next((r for r in results_for_claim if r["sq_id"] == sq_id), None)
            if match:
                score = match["relevance"]
                if score >= 0.7:
                    cell = f"**{score:.2f}**"
                elif score >= 0.4:
                    cell = f"{score:.2f}"
                elif score > 0.0:
                    cell = f"*{score:.2f}*"
                else:
                    cell = "0.00"
                row.append(cell)
                if score > best_score:
                    best_score = score
                    best_sq = sq_id
            else:
                row.append("-")
        row.append(f"{best_sq} ({best_score:.2f})")
        rows.append(row)
    report.table(headers, rows)

    # Detailed reasoning per pair
    report.h3("Razonamiento del Judge (detalle)")
    for claim in CLAIMS:
        cid = claim["claim_id"]
        report.p(f"**{cid}:** _{claim['claim_text'][:80]}..._")
        for r in by_claim.get(cid, []):
            score = r["relevance"]
            if score >= 0.7:
                marker = "RELEVANTE"
            elif score >= 0.4:
                marker = "TANGENCIAL"
            elif score > 0.0:
                marker = "DEBIL"
            else:
                marker = "IRRELEVANTE"
            report.bullet(
                f"vs **{r['sq_id']}**: {score:.2f} [{marker}] -- "
                f"{r['reasoning']}"
            )
        report.blank()


def step_score(report: ReportBuilder, relevance_results, compiled_sqs):
    """Document how the final score would be computed."""
    report.h2("6. Composicion del Score")
    report.p(
        "El score final combina tres dimensiones:"
    )
    report.bullet("**Truth** (verdad): el claim es correcto segun el SCM? (0 o 1)")
    report.bullet("**Relevance** (relevancia): el claim es relevante para algun SQ? (0.0-1.0)")
    report.bullet("**Tier weight** (peso): high=1.0, medium=0.6, low=0.3")
    report.blank()
    report.p("**Formula por claim:**")
    report.code("claim_score = truth * max_relevance * tier_weight_of_best_sq")
    report.p("**Score del episodio:**")
    report.code(
        "correctness = mean(truth_i for all claims)\n"
        "coverage = sum(claim_score_i) / sum(tier_weight_j for all SQs)\n"
        "total = correctness * coverage"
    )

    # Worked example
    report.h3("Ejemplo trabajado (con truth simulado)")
    report.p(
        "No tenemos compilacion real de los claims a AtomicSpecs, asi que "
        "simulamos truth para ilustrar. En el E2E real, truth se computa "
        "ejecutando los specs compilados contra el SCM."
    )

    tier_weights = {"high": 1.0, "medium": 0.6, "low": 0.3}
    sq_tiers = {sq["sq_id"]: sq["tier"] for sq in compiled_sqs}

    # Simulate truth: c1-c3 true, c4-c5 false/irrelevant
    simulated_truth = {"c1": 1.0, "c2": 1.0, "c3": 1.0, "c4": 0.0, "c5": 0.0}

    by_claim: dict[str, list] = {}
    for r in relevance_results:
        by_claim.setdefault(r["claim_id"], []).append(r)

    headers = ["Claim", "Truth", "Best SQ", "Relevance", "Tier", "Weight", "Score"]
    rows = []
    total_weight = sum(tier_weights[sq["tier"]] for sq in compiled_sqs)
    total_claim_score = 0.0
    truths = []

    for claim in CLAIMS:
        cid = claim["claim_id"]
        truth = simulated_truth.get(cid, 0.0)
        truths.append(truth)

        # Find best relevance
        best_rel = 0.0
        best_sq = "-"
        for r in by_claim.get(cid, []):
            if r["relevance"] > best_rel:
                best_rel = r["relevance"]
                best_sq = r["sq_id"]

        tier = sq_tiers.get(best_sq, "low")
        tw = tier_weights.get(tier, 0.3)
        score = truth * best_rel * tw
        total_claim_score += score

        rows.append([
            cid,
            f"{truth:.0f}",
            best_sq,
            f"{best_rel:.2f}",
            tier,
            f"{tw:.1f}",
            f"{score:.3f}",
        ])

    report.table(headers, rows)

    correctness = sum(truths) / len(truths) if truths else 0.0
    coverage = total_claim_score / total_weight if total_weight > 0 else 0.0
    total = correctness * coverage

    report.p(f"**Correctness** = {sum(truths):.0f}/{len(truths)} = {correctness:.2f}")
    report.p(f"**Coverage** = {total_claim_score:.3f} / {total_weight:.1f} = {coverage:.3f}")
    report.p(f"**Total** = {correctness:.2f} x {coverage:.3f} = **{total:.3f}**")
    report.blank()
    report.p(
        "Nota: c4 y c5 tienen truth=0 porque son irrelevantes o hablan de "
        "variables que no existen. En el E2E real, truth se determina "
        "compilando el claim a AtomicSpecs y ejecutandolos contra el SCM."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Inspect scoring pipeline")
    parser.add_argument(
        "--from-json",
        help="Generate report from existing JSON (no LLM calls)",
    )
    args = parser.parse_args()

    report = ReportBuilder()

    if args.from_json:
        # -- Offline mode: read from JSON --
        logger.info("Loading data from %s ...", args.from_json)
        with open(args.from_json, encoding="utf-8") as f:
            data = json.load(f)

        compiled_sqs = data["sqs"]
        claims_data = data["claims"]
        relevance_results = data["relevance_results"]

        # Use world for DAG visualization
        logger.info("Loading world for DAG info...")
        world = load_world()
        step_world(report, world)
        step_brief(report)
        step_sqs(report, compiled_sqs)
        step_claims(report)
        step_relevance(report, relevance_results, compiled_sqs)
        step_score(report, relevance_results, compiled_sqs)

    else:
        # -- Online mode: run full pipeline with LLM --
        logger.info("Loading world...")
        world = load_world()
        step_world(report, world)
        step_brief(report)

        logger.info("Setting up LLM...")
        llm_call = make_llm_call()

        # -- Compile and ground SQs --
        logger.info("Compiling SQs...")
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
            logger.info("  Compiling %s: %s", raw["sq_id"], raw["text_gloss"][:60])
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

            gr = ground_sq_answer_key(result.sq, world, solver, seed=42)
            if not gr.success:
                logger.warning("  GROUNDING FAILED: %s", gr.warnings)
                continue

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
            logger.info("  OK: %d answer keys", len(answer_keys))

        if not compiled_sqs:
            logger.error("No SQs compiled -- aborting")
            return

        logger.info("Compiled %d/%d SQs", len(compiled_sqs), len(RAW_SQS))
        step_sqs(report, compiled_sqs)
        step_claims(report)

        logger.info("Running relevance judge...")
        from sreg.tools.oi_relevance_judge import judge_all_claims

        relevance_results = judge_all_claims(
            claims=CLAIMS,
            sqs=compiled_sqs,
            brief_text=BRIEF_TEXT,
            llm_call=llm_call,
        )
        logger.info("Judge complete: %d pairs scored", len(relevance_results))

        step_relevance(report, relevance_results, compiled_sqs)
        step_score(report, relevance_results, compiled_sqs)

        # Save raw data for future offline runs
        json_path = "results/pipeline_inspection.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "brief": BRIEF_TEXT,
                "sqs": compiled_sqs,
                "claims": CLAIMS,
                "relevance_results": relevance_results,
            }, f, indent=2, default=str)
        logger.info("Raw data saved to %s", json_path)

    # -- Write report --
    out_path = "results/pipeline_inspection.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report.get())
    logger.info("Report written to %s", out_path)


if __name__ == "__main__":
    main()
