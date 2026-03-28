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
from test_oi_curated_worlds import world_ecosystem, world_treatment, world_education

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
        target_states=["low", "medium", "high"],
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
    world_name: str,
    world: SCMWorld,
    problem: ResearchProblem,
    result: OIInvestigationResult,
    salience,
    elapsed: float,
    solver_model: str,
    compiler_model: str,
) -> str:
    """Build a full_case_oi.md report."""
    lines = []

    # Header
    lines.append(f"# Open Investigation Case Report: {problem.title}")
    lines.append("")
    lines.append(f"> **Domain:** {problem.domain}")
    lines.append(f"> **Solver:** {solver_model} | **Compiler:** {compiler_model}")
    lines.append(f"> **Investigation steps:** {result.n_steps} | "
                 f"**Time:** {elapsed:.0f}s")
    lines.append(f"> **Status:** Work in progress (Alpha-0)")
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

    # Salience map
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
    lines.append("Each claim is compiled by an LLM into a formal AtomicSpec, "
                 "matched against salience map families, and verified via "
                 "Monte Carlo simulation against the SCM. No LLM judge is "
                 "used for scoring -- verification is exact.")
    lines.append("")

    if result.score:
        s = result.score
        lines.append("## Overall score")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| **Total** | **{s.total:.3f}** |")
        lines.append(f"| Correctness | {s.correctness:.3f} |")
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

        if s.claim_verdicts:
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
        hit = ""  # We don't have easy matching info here
        lines.append(f"- {fam.key.pattern_class}: [{focus}]")
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

    salience = build_salience_map(world, cfg["target"], n_mc=N_MC, seed=SEED)

    print(f"  Done: {result.n_steps} steps, {elapsed:.0f}s")
    if result.score:
        print(f"  Score: total={result.score.total:.3f} "
              f"correctness={result.score.correctness:.3f} "
              f"coverage={result.score.coverage:.3f}")

    # Build and save report
    report = build_report(
        args.world, world, problem, result, salience,
        elapsed, solver_model, compiler_model,
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
