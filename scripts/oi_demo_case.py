"""Generate a full OI case report for demo purposes.

Runs one Open Investigation pilot and produces full_case_oi.md with:
  Part 0: Ground truth (hidden causal model)
  Part 1: What the solver received (vague brief + data)
  Part 2: What the solver did (full investigation trace)
  Part 3: Claims submitted
  Part 4: How claims were compiled and scored

Usage:
    python scripts/oi_demo_case.py --world treatment --output experiments/oi_treatment
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_driver import OIInvestigationResult, run_oi_investigation
from sreg.tools.oi_runner import OIEpisodeRunner
from sreg.tools.oi_salience import build_salience_map
from sreg.world.scm import SCMWorld

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "tools"))
from test_oi_curated_worlds import (
    world_ecosystem, world_treatment, world_education,
    world_treatment_simpson, world_productivity, world_screen_time,
)

N_MC = 20_000
SEED = 42

WORLDS = {
    "ecosystem": {
        "factory": world_ecosystem,
        "target": "Fish",
        "brief": (
            "A research team has collected observational data on a freshwater "
            "lake ecosystem. Variables include sunlight exposure, water "
            "temperature, nutrient concentration, algae density, water depth, "
            "and fish population counts across 300 sampling sites.\n\n"
            "Your task: Investigate the factors that drive fish population "
            "variation across sites. What are the main determinants? Are there "
            "interaction effects or confounding relationships?"
        ),
        "domain": "Freshwater ecology",
    },
    "treatment": {
        "factory": world_treatment,
        "target": "Recovery",
        "brief": (
            "A hospital collected observational data on 300 patients who "
            "received varying levels of a treatment. Variables include patient "
            "age, disease severity at admission, treatment dosage, a biomarker "
            "measured during treatment, and recovery score at discharge.\n\n"
            "Your task: Investigate why treatment outcomes varied across "
            "patients. Does the treatment help recovery? Through what "
            "mechanism? Are there confounding factors?"
        ),
        "domain": "Clinical outcomes research",
    },
    "education": {
        "factory": world_education,
        "target": "Income",
        "brief": (
            "A longitudinal study tracked 300 individuals, measuring family "
            "wealth, personal motivation scores, years of education, skill "
            "assessment scores, and current income.\n\n"
            "Your task: Investigate the determinants of income inequality. "
            "What role does education play? Is the education-income "
            "relationship confounded? Are there mediating pathways?"
        ),
        "domain": "Labor economics",
    },
    "productivity": {
        "factory": world_productivity,
        "target": "Productivity",
        "brief": (
            "A consulting firm collected data on 300 project teams. Variables "
            "include team size, average member experience, training hours, "
            "and a productivity index.\n\n"
            "Your task: Investigate what drives team productivity. Does "
            "training help? What role does team size play?"
        ),
        "domain": "Organizational productivity",
    },
    "screen_time": {
        "factory": world_screen_time,
        "target": "Academic",
        "brief": (
            "A school district collected data on 300 students. Variables "
            "include parental income, motivation, daily screen time, weekly "
            "physical activity, and academic performance.\n\n"
            "Your task: Investigate factors affecting academic performance. "
            "Does screen time help or hurt? Are there confounding factors?"
        ),
        "domain": "Educational research",
    },
}


def _problem_from_world(world, target, brief, domain, n_rows=300):
    df = world.sample(n_rows, seed=SEED)
    asset = DataAsset(
        artifact_id="dataset_main",
        name="main_study",
        description="Observational study data",
        format="tabular",
        data=df.to_dict("records"),
        columns=list(df.columns),
        num_rows=n_rows,
    )
    return ResearchProblem(
        world_id=world.id,
        title=f"Open Investigation: {domain}",
        description=brief,
        domain=domain,
        data_assets=[asset],
        available_actions=[],
        budget=10,
        research_question=brief,
        target_node=target,
    )


def make_llm_compiler(client, model):
    def llm_call(messages):
        system_msg = user_msg = None
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            elif m["role"] == "user":
                user_msg = m["content"]
        kwargs = {"model": model, "input": user_msg or ""}
        if system_msg:
            kwargs["instructions"] = system_msg
        response = client.responses.create(**kwargs)
        text = ""
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        text += part.text
        return text
    return llm_call


def build_report(
    result_or_world_name,
    world: SCMWorld = None,
    problem: ResearchProblem = None,
    result: OIInvestigationResult = None,
    salience=None,
    elapsed: float = 0,
    solver_model: str = "?",
    compiler_model: str = "?",
    runner=None,
    sub_questions=None,
) -> str:
    """Build a full_case_oi.md report.

    Supports two call signatures:
    - build_report(result, world, problem) — from generate_src.py
    - build_report(world_name, world, problem, result, ...) — standalone
    """
    # Handle generate_src.py signature: build_report(oi_result, world, problem)
    if isinstance(result_or_world_name, OIInvestigationResult):
        result = result_or_world_name
        # world and problem already in their positions
    elif isinstance(result_or_world_name, str):
        pass  # world_name string, result is in kwarg
    else:
        result = result_or_world_name  # best effort

    if result is None:
        return "# Error: no investigation result provided\n"

    # Salience map is optional (diagnostic only, not in E2E critical path)
    # Pass salience= explicitly if you want Part 4 coverage analysis

    lines = []

    # Header
    title = problem.title if problem else "Open Investigation"
    domain = problem.domain if problem else "Research"
    lines.append(f"# Open Investigation Case Report: {title}")
    lines.append("")
    lines.append(f"> **Domain:** {domain}")
    lines.append(f"> **Solver:** {solver_model} | **Compiler:** {compiler_model}")
    lines.append(f"> **Investigation steps:** {result.n_steps} | "
                 f"**Time:** {elapsed:.0f}s")
    lines.append("")

    # =========================================================
    # Part 0: Ground truth
    # =========================================================
    lines.append("---")
    lines.append("")
    lines.append("# Part 0: Ground truth (hidden from the solver)")
    lines.append("")
    lines.append("The solver never sees this section. This is the structural causal "
                 "model (SCM) that generated the data and against which all claims "
                 "are verified.")
    lines.append("")

    # Mermaid DAG
    lines.append("## Causal DAG")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")
    for var in world.variables:
        label = var.replace("_", " ").title()
        lines.append(f'    {var}["{label}"]')
    lines.append("")
    for child, parents in world.graph.items():
        for parent in parents:
            lines.append(f"    {parent} --> {child}")
    lines.append("```")
    lines.append("")

    # Equations
    lines.append("## Structural equations")
    lines.append("")
    for var in world.variables:
        eq_fn = world.equations.get(var)
        doc = eq_fn.__doc__ if eq_fn and eq_fn.__doc__ else None
        if doc:
            lines.append(f"- **{var}**: `{doc}`")
        else:
            # Try to get source hint from parents
            parents = world.graph.get(var, [])
            if parents:
                lines.append(f"- **{var}**: f({', '.join(parents)}) + noise")
            else:
                lines.append(f"- **{var}**: exogenous (root node)")
    lines.append("")

    # Salience map (optional — only when computed for diagnostics)
    if salience:
        lines.append("## Salience map (discoverable truths)")
        lines.append("")
        lines.append(f"The salience map enumerates {len(salience.families)} families of "
                     f"verifiable facts about this world:")
        lines.append("")
        for fam in salience.families:
            focus = ", ".join(fam.key.focus_signature)
            lines.append(f"- **{fam.key.pattern_class}** [{focus}] "
                         f"({len(fam.atoms)} atoms)")
        lines.append("")

    # =========================================================
    # Part 1: What the solver received
    # =========================================================
    lines.append("---")
    lines.append("")
    lines.append("# Part 1: What the solver received")
    lines.append("")
    lines.append("The solver receives only a vague research brief and a dataset. "
                 "No specific questions, no answer format, no hints about the "
                 "causal structure. It must decide what to investigate and what "
                 "to conclude.")
    lines.append("")
    lines.append("## Research brief")
    lines.append("")
    lines.append(f"> {problem.research_question}")
    lines.append("")
    lines.append("## Dataset")
    lines.append("")
    for asset in problem.data_assets:
        lines.append(f"- **{asset.artifact_id}**: {asset.num_rows} rows, "
                     f"columns: {', '.join(asset.columns or [])}")
    lines.append("")
    lines.append("The solver has access to: `python_exec` (persistent Python "
                 "interpreter with pandas, numpy, scipy), instrumented helpers "
                 "(`oi.corr`, `oi.regress`, `oi.stratify`, `oi.test_independence`), "
                 "and `submit_claims` to deliver findings.")
    lines.append("")

    # =========================================================
    # Part 2: What the solver did
    # =========================================================
    lines.append("---")
    lines.append("")
    lines.append("# Part 2: What the solver did")
    lines.append("")
    lines.append("Complete investigation trace. The solver autonomously decided "
                 "what analyses to run and when to submit findings.")
    lines.append("")

    for msg in result.messages:
        role = msg.get("role", "?")

        if role == "system":
            lines.append("> *(system prompt: instructs solver to investigate, "
                         "use causal language only when evidence supports it)*")
            lines.append("")

        elif role == "user":
            content = msg.get("content", "")
            if len(content) > 300:
                content = content[:300] + "..."
            lines.append(f"> **[BRIEFING]** {content}")
            lines.append("")

        elif role == "assistant":
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if content and content.strip():
                lines.append("**[SOLVER THINKS]**")
                lines.append("")
                lines.append(content)
                lines.append("")

            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "?")
                fn_args_raw = fn.get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}

                if fn_name == "think":
                    reasoning = fn_args.get("reasoning", "")
                    lines.append("**[SOLVER REASONS]**")
                    lines.append("")
                    lines.append(f"> {reasoning}")
                    lines.append("")

                elif fn_name == "python_exec":
                    code = fn_args.get("code", "")
                    lines.append("**[SOLVER RUNS CODE]**")
                    lines.append("```python")
                    lines.append(code)
                    lines.append("```")
                    lines.append("")

                elif fn_name == "submit_claims":
                    claims = fn_args.get("claims", [])
                    lines.append(f"**[SOLVER SUBMITS {len(claims)} CLAIMS]**")
                    lines.append("")
                    for c in claims:
                        lines.append(f"**Claim {c.get('claim_id', '?')}:** "
                                     f"{c.get('claim_text', '')}")
                        lines.append(f"- Variables: {c.get('focus_variables', [])}")
                        lines.append(f"- Confidence: {c.get('confidence', '?')}")
                        lines.append(f"- Tags: {c.get('pattern_tags', [])}")
                        lines.append("")

        elif role == "tool":
            content = msg.get("content", "")
            # Skip system confirmations
            if '"status": "noted"' in content:
                continue
            if '"status": "submitted"' in content:
                lines.append("**[CLAIMS RECORDED]** Investigation complete.")
                lines.append("")
                continue
            # Code output
            if len(content) > 1500:
                content = content[:1500] + "\n... (truncated)"
            lines.append("**[OUTPUT]**")
            lines.append("```")
            lines.append(content)
            lines.append("```")
            lines.append("")

    # =========================================================
    # Part 3: Claims submitted
    # =========================================================
    lines.append("---")
    lines.append("")
    lines.append("# Part 3: Claims submitted")
    lines.append("")
    lines.append("The solver submitted these natural-language findings. "
                 "Each claim is compiled into formal specs and verified "
                 "against the SCM.")
    lines.append("")

    # Extract claims from conversation
    for msg in result.messages:
        if msg.get("role") == "assistant":
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                if fn.get("name") == "submit_claims":
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    for c in args.get("claims", []):
                        lines.append(f"### {c.get('claim_id', '?')}")
                        lines.append("")
                        lines.append(f"> {c.get('claim_text', '')}")
                        lines.append("")
                        lines.append(f"- **Variables:** {', '.join(c.get('focus_variables', []))}")
                        lines.append(f"- **Confidence:** {c.get('confidence', '?')}")
                        lines.append(f"- **Pattern tags:** {', '.join(c.get('pattern_tags', []))}")
                        eb = c.get("evidence_basis", [])
                        if eb:
                            lines.append(f"- **Evidence:** {eb[0].get('rationale', '')}")
                        lines.append("")

    # =========================================================
    # Part 4: Evaluation
    # =========================================================
    lines.append("---")
    lines.append("")
    lines.append("# Part 4: How claims were evaluated")
    lines.append("")
    lines.append("Each claim is compiled by an LLM into a formal AtomicSpec "
                 "and verified via Monte Carlo simulation against the SCM. "
                 "No LLM judge is used for scoring -- verification is exact.")
    lines.append("")

    if result.score:
        s = result.score
        lines.append("## Overall score")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| **Total** | **{s.total:.3f}** |")
        lines.append(f"| Correctness | {s.correctness:.3f} |")

        # Handle both EpisodeScore (v1) and EpisodeSubQuestionScore (v2)
        from sreg.models.open_investigation import EpisodeSubQuestionScore
        if isinstance(s, EpisodeSubQuestionScore):
            lines.append(f"| Coverage | {s.coverage:.3f} |")
            lines.append(f"| Weighted Coverage | {s.weighted_coverage:.3f} |")
            lines.append("")
            lines.append("**Score formula:** total = correctness x weighted_coverage")
            lines.append("")
            if s.sq_scores:
                lines.append("### Per-SQ scores")
                lines.append("")
                lines.append("| SQ | Satisfaction | Best Claim | Matched |")
                lines.append("|-----|-------------|------------|---------|")
                for sq in s.sq_scores:
                    lines.append(
                        f"| {sq.sq_id} | {sq.satisfaction:.3f} | "
                        f"{sq.best_claim_id or '-'} | "
                        f"{'yes' if sq.matched else 'no'} |"
                    )
                lines.append("")
        else:
            lines.append(f"| Coverage | {s.coverage:.3f} |")
            lines.append(f"| Efficiency | {s.efficiency:.3f} |")
            lines.append(f"| Families hit | {s.families_hit} / {s.families_total} |")
            lines.append(f"| Precision gate | {'active' if s.precision_gate_active else 'inactive'} |")
            lines.append("")
            lines.append("**Score formula:** "
                         f"{s.W_CORRECTNESS:.0%} correctness + "
                         f"{s.W_COVERAGE:.0%} coverage + "
                         f"{s.W_EFFICIENCY:.0%} efficiency")
            lines.append("")

        if hasattr(s, "claim_verdicts") and s.claim_verdicts:
            lines.append("## Per-claim verdicts")
            lines.append("")
            lines.append("| Claim | Verdict | Score | Matched family |")
            lines.append("|-------|---------|-------|----------------|")
            for cv in s.claim_verdicts:
                fam = cv.matched_family_id or "unmatched"
                lines.append(f"| {cv.claim_id} | {cv.verdict} | "
                             f"{cv.score:.3f} | {fam} |")
            lines.append("")

    # Coverage analysis
    if salience:
        lines.append("## What was discovered vs what exists")
        lines.append("")
        lines.append(f"The salience map contains {len(salience.families)} families "
                     f"of verifiable truths. The solver's claims matched "
                     f"{result.score.families_hit if result.score else '?'} of them.")
        lines.append("")
        lines.append("Families in the salience map:")
        lines.append("")
        for fam in salience.families:
            focus = ", ".join(fam.key.focus_signature)
            lines.append(f"- {fam.key.pattern_class}: [{focus}]")
        lines.append("")

    # =========================================================
    # Part 5: Sub-question evaluation (hidden agenda)
    # =========================================================
    sq_score = runner.get_sq_score() if runner else None
    if sub_questions or sq_score:
        tier_weights = {"high": 1.0, "medium": 0.6, "low": 0.3}

        lines.append("---")
        lines.append("")
        lines.append("# Part 5: Hidden evaluation agenda (sub-questions)")
        lines.append("")
        lines.append("The orchestrator generated these sub-questions when designing "
                     "the case. The solver **never sees them** -- they represent "
                     "what a good investigation should discover. Each sub-question "
                     "is verified exactly against the SCM (no LLM judge).")
        lines.append("")
        lines.append("Tier weights: **HIGH** = 1.0, **MEDIUM** = 0.6, **LOW** = 0.3")
        lines.append("")

        if sub_questions:
            lines.append("## Sub-questions (hidden from solver)")
            lines.append("")
            for sq in sub_questions:
                tier_w = tier_weights.get(sq.tier, 0.5)
                gloss = sq.text_gloss or sq.pattern
                lines.append(f"### {sq.sq_id} -- {gloss}")
                lines.append("")
                roles_parts = []
                if sq.roles.treatment:
                    roles_parts.append(f"Treatment: `{sq.roles.treatment}`")
                if sq.roles.outcome:
                    roles_parts.append(f"Outcome: `{sq.roles.outcome}`")
                if sq.roles.mediator:
                    roles_parts.append(f"Mediator: `{sq.roles.mediator}`")
                if sq.roles.modifier:
                    roles_parts.append(f"Modifier: `{sq.roles.modifier}`")
                if sq.roles.confounder:
                    roles_parts.append(f"Confounder: `{sq.roles.confounder}`")
                if sq.roles.ranking_vars:
                    rv = ", ".join(f"`{v}`" for v in sq.roles.ranking_vars)
                    roles_parts.append(f"Ranking: {rv}")
                lines.append(f"- **Pattern:** {sq.pattern} | "
                             f"**Ask:** {sq.ask} | "
                             f"**Tier:** {sq.tier.upper()} (weight {tier_w})")
                for rp in roles_parts:
                    lines.append(f"- {rp}")
                lines.append("")

        if sq_score:
            lines.append("## Sub-question results")
            lines.append("")

            # Per-SQ results with gloss
            sq_map = {sq.sq_id: sq for sq in sub_questions} if sub_questions else {}
            for s in sq_score.sq_scores:
                sq_def = sq_map.get(s.sq_id)
                gloss = sq_def.text_gloss if sq_def and sq_def.text_gloss else s.sq_id
                tier_label = sq_def.tier.upper() if sq_def else "?"
                status = "HIT" if s.matched else "MISS"
                icon = "+" if s.matched else "-"
                claim_str = f" -- matched by **{s.best_claim_id}**" if s.best_claim_id else ""
                lines.append(f"- [{icon}] **{s.sq_id}** ({tier_label}): "
                             f"{gloss} -- "
                             f"satisfaction {s.satisfaction:.2f} "
                             f"[{status}]{claim_str}")
            lines.append("")

            lines.append("## Aggregate SQ score")
            lines.append("")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| **SQ Total** | **{sq_score.total:.3f}** |")
            lines.append(f"| Weighted coverage | {sq_score.weighted_coverage:.3f} |")
            lines.append(f"| Correctness | {sq_score.correctness:.3f} |")
            lines.append(f"| Novel bonus | {sq_score.novel_bonus:.3f} |")
            lines.append("")
            lines.append("Formula: `SQ_total = weighted_coverage * 0.70 "
                         "+ correctness * 0.20 + novel_bonus * 0.10`")
            lines.append("")

    # =========================================================
    # Summary
    # =========================================================
    lines.append("---")
    lines.append("")
    lines.append("# Summary")
    lines.append("")
    if result.score:
        s = result.score
        if hasattr(s, "claim_verdicts"):
            n_true = sum(1 for cv in s.claim_verdicts if cv.score > 0.5)
            n_total = len(s.claim_verdicts)
            lines.append(f"The solver submitted **{n_total} claims**, of which "
                         f"**{n_true}** were verified as true against the SCM "
                         f"(correctness {s.correctness:.0%}).")
        else:
            lines.append(f"Correctness: **{s.correctness:.0%}** "
                         f"(mean truth of all claims).")
        lines.append("")
    if sq_score and sub_questions:
        n_hit = sum(1 for s in sq_score.sq_scores if s.matched)
        n_sq = len(sq_score.sq_scores)
        lines.append(f"Of **{n_sq} hidden sub-questions**, the solver's claims "
                     f"addressed **{n_hit}** ({n_hit}/{n_sq}).")
        lines.append("")
    lines.append("**Key:** All verification is exact (Monte Carlo simulation "
                 "against the structural causal model). No LLM judges are used "
                 "in scoring. The solver decides autonomously what to investigate, "
                 "what analyses to run, and what to conclude.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="OI Demo Case Generator")
    parser.add_argument("--world", type=str, default="treatment",
                        choices=list(WORLDS.keys()))
    parser.add_argument("--output", type=str, default="experiments/oi_demo")
    args = parser.parse_args()

    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL")
    compiler_model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    solver_model = os.environ.get("AZURE_SOLVER_MODEL", "gpt-5.2-codex")

    if not base_url or not api_key:
        print("ERROR: Missing AZURE_FOUNDRY_BASE_URL or AZURE_INFERENCE_CREDENTIAL")
        sys.exit(1)

    client = OpenAI(base_url=base_url, api_key=api_key)

    cfg = WORLDS[args.world]
    world = cfg["factory"]()
    problem = _problem_from_world(world, cfg["target"], cfg["brief"], cfg["domain"])
    llm_compiler = make_llm_compiler(client, compiler_model)
    runner = OIEpisodeRunner(
        problem, world, seed=SEED, n_mc=N_MC, llm_call=llm_compiler,
    )

    print(f"Running OI investigation: {args.world}")
    print(f"  Solver: {solver_model} | Compiler: {compiler_model}")

    t0 = time.time()
    result = run_oi_investigation(
        runner, client, solver_model,
        max_iterations=20, temperature=None,
    )
    elapsed = time.time() - t0

    print(f"  Done: {result.n_steps} steps, {elapsed:.0f}s")

    # Wire sub-questions for curated worlds (from oi_pilot_batch)
    sqs = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from oi_pilot_batch import WORLD_SQS
        if args.world in WORLD_SQS:
            sqs = WORLD_SQS[args.world]
            runner.set_subquestions(sqs)
            print(f"  SQs: {len(sqs)} manual sub-questions loaded")
    except ImportError:
        pass

    # Build and save report
    report = build_report(
        args.world, world, problem, result,
        elapsed, solver_model, compiler_model,
        runner=runner, sub_questions=sqs,
    )

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "full_case_oi.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Report: {report_path}")

    # Also save raw JSON
    raw_path = out_dir / "oi_result.json"
    raw_data = {
        "world": args.world,
        "solver_model": solver_model,
        "compiler_model": compiler_model,
        "elapsed": elapsed,
        "n_steps": result.n_steps,
        "submitted": result.submitted,
        "score": result.score.model_dump() if result.score else None,
        "conversation": result.messages,
    }
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Raw JSON: {raw_path}")


if __name__ == "__main__":
    main()
