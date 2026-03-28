"""OI Pilot Batch: run 3 curated worlds with real LLM solver + compiler.

Usage:
    python scripts/oi_pilot_batch.py [--runs N] [--world NAME] [--out DIR]

Runs all 3 curated worlds (ecosystem, treatment, education) with the full
OI pipeline (LLM solver + LLM compiler, warrant disabled). Saves results
to JSON + readable text for qualitative analysis.

Requires .env with: AZURE_INFERENCE_CREDENTIAL, AZURE_FOUNDRY_BASE_URL,
AZURE_MODEL (compiler), AZURE_SOLVER_MODEL (solver).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix Windows encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# Load .env before any Azure imports
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# Project imports
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_driver import OIInvestigationResult, run_oi_investigation
from sreg.tools.oi_runner import OIEpisodeRunner
from sreg.tools.oi_salience import build_salience_map
from sreg.tools.oi_compiler import CompilerOutput
from sreg.world.scm import SCMWorld

# Import curated worlds from test module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "tools"))
from test_oi_curated_worlds import (
    world_ecosystem,
    world_treatment,
    world_education,
)

N_MC = 20_000
SEED = 42


# ---------------------------------------------------------------------------
# World definitions with briefs
# ---------------------------------------------------------------------------

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
    },
}


def _problem_from_world(
    world: SCMWorld, target: str, brief: str, n_rows: int = 300,
) -> ResearchProblem:
    """Generate a ResearchProblem with sampled data from an SCMWorld."""
    df = world.sample(n_rows, seed=SEED)
    cols = list(df.columns)
    records = df.to_dict("records")

    asset = DataAsset(
        artifact_id="dataset_main",
        name="main_study",
        description="Observational study data",
        format="tabular",
        data=records,
        columns=cols,
        num_rows=n_rows,
    )

    return ResearchProblem(
        world_id=world.id,
        title=f"Investigation: {world.id}",
        description=brief,
        domain="research",
        data_assets=[asset],
        available_actions=[],
        budget=10,
        research_question=brief,
        target_node=target,
        target_states=["low", "medium", "high"],
    )


def make_llm_compiler(client: OpenAI, model: str):
    """Create an llm_call function for the compiler.

    The compiler expects: llm_call(messages) -> str
    where messages is a list of chat-format dicts.
    """
    def llm_call(messages: list[dict]) -> str:
        # Convert chat messages to Responses API format
        system_msg = None
        user_msg = None
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            elif m["role"] == "user":
                user_msg = m["content"]

        kwargs: dict = {"model": model, "input": user_msg or ""}
        if system_msg:
            kwargs["instructions"] = system_msg

        response = client.responses.create(**kwargs)

        # Extract text from response
        text = ""
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        text += part.text
        return text

    return llm_call


def run_single_pilot(
    world_name: str,
    run_id: int,
    client: OpenAI,
    solver_model: str,
    compiler_model: str,
) -> dict:
    """Run a single OI pilot and return structured results."""
    cfg = WORLDS[world_name]
    world = cfg["factory"]()
    problem = _problem_from_world(world, cfg["target"], cfg["brief"])

    llm_compiler = make_llm_compiler(client, compiler_model)
    runner = OIEpisodeRunner(
        problem, world, seed=SEED + run_id, n_mc=N_MC, llm_call=llm_compiler,
    )

    print(f"\n{'='*70}")
    print(f"  PILOT: {world_name} (run {run_id})")
    print(f"  Solver: {solver_model} | Compiler: {compiler_model}")
    print(f"{'='*70}")

    t0 = time.time()
    result = run_oi_investigation(
        runner, client, solver_model,
        max_iterations=20, temperature=None,
    )
    elapsed = time.time() - t0

    # Build salience map for reference
    salience = build_salience_map(world, cfg["target"], n_mc=N_MC, seed=SEED)

    # Extract conversation details
    conversation = _extract_conversation(result)
    claims_detail = _extract_claims_detail(runner, result)
    salience_detail = _extract_salience_detail(salience)

    output = {
        "world": world_name,
        "run_id": run_id,
        "solver_model": solver_model,
        "compiler_model": compiler_model,
        "elapsed_seconds": round(elapsed, 1),
        "n_steps": result.n_steps,
        "submitted": result.submitted,
        "score": None,
        "score_detail": None,
        "conversation": conversation,
        "claims": claims_detail,
        "salience_families": salience_detail,
    }

    if result.score:
        output["score"] = {
            "total": round(result.score.total, 4),
            "correctness": round(result.score.correctness, 4),
            "coverage": round(result.score.coverage, 4),
            "efficiency": round(result.score.efficiency, 4),
            "families_hit": result.score.families_hit,
            "families_total": result.score.families_total,
            "precision_gate": result.score.precision_gate_active,
        }
        output["score_detail"] = {
            "per_claim": [
                {
                    "claim_id": cv.claim_id,
                    "score": round(cv.score, 4),
                    "verdict": cv.verdict,
                    "matched_family_id": cv.matched_family_id,
                    "n_atoms": len(cv.atom_verdicts),
                }
                for cv in result.score.claim_verdicts
            ],
        }

    # Print summary
    _print_summary(output)

    return output


def _extract_conversation(result: OIInvestigationResult) -> list[dict]:
    """Extract readable conversation from messages."""
    conv = []
    for msg in result.messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")

        if role == "system":
            conv.append({"role": "system", "content": content[:200] + "..."})
        elif role == "user":
            conv.append({"role": "user", "content": content[:500]})
        elif role == "assistant":
            entry: dict = {"role": "assistant", "content": content[:500] if content else ""}
            if msg.get("tool_calls"):
                entry["tool_calls"] = []
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    tool_entry = {"name": fn.get("name", "?")}
                    args_str = fn.get("arguments", "{}")
                    # Truncate long code
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        if isinstance(args, dict) and "code" in args:
                            args["code"] = args["code"][:500]
                        if isinstance(args, dict) and "claims" in args:
                            tool_entry["claims_summary"] = [
                                {
                                    "id": c.get("claim_id", "?"),
                                    "text": c.get("claim_text", "")[:200],
                                    "vars": c.get("focus_variables", []),
                                    "tags": c.get("pattern_tags", []),
                                }
                                for c in args["claims"]
                            ]
                            args = {"claims": f"[{len(args['claims'])} claims]"}
                        tool_entry["args"] = args
                    except (json.JSONDecodeError, TypeError):
                        tool_entry["args_raw"] = args_str[:200]
                    entry["tool_calls"].append(tool_entry)
            conv.append(entry)
        elif role == "tool":
            content_str = str(content)[:800]
            conv.append({"role": "tool", "content": content_str})

    return conv


def _extract_claims_detail(
    runner: OIEpisodeRunner, result: OIInvestigationResult
) -> list[dict]:
    """Extract claim details including compilation results."""
    if not result.score or not result.score.claim_verdicts:
        return []

    details = []
    for cv in result.score.claim_verdicts:
        detail: dict = {
            "claim_id": cv.claim_id,
            "score": round(cv.score, 4),
            "verdict": cv.verdict,
            "matched_family_id": cv.matched_family_id,
            "atom_verdicts": [
                {
                    "atom_id": av.atom_id,
                    "holds": av.solver_assertion_holds,
                    "score": round(av.score, 4),
                    "assertion": str(av.spec.assertion),
                }
                for av in cv.atom_verdicts
            ],
        }
        details.append(detail)
    return details


def _extract_salience_detail(salience) -> list[dict]:
    """Extract salience map families for reference."""
    families = []
    for fam in salience.families:
        entry = {
            "pattern": fam.key.pattern_class,
            "focus": list(fam.key.focus_signature),
            "brief_target": fam.key.brief_target,
            "n_atoms": len(fam.atoms),
        }
        if fam.atoms:
            a0 = fam.atoms[0]
            entry["example_atom"] = {
                "assertion": str(a0.spec.assertion),
                "comparison": str(a0.spec.comparison),
            }
        families.append(entry)
    return families


def _print_summary(output: dict) -> None:
    """Print a human-readable summary of a pilot run."""
    print(f"\n--- {output['world']} run {output['run_id']} ---")
    print(f"Steps: {output['n_steps']} | Time: {output['elapsed_seconds']}s")
    print(f"Submitted: {output['submitted']}")

    if output["score"]:
        s = output["score"]
        print(f"Score: total={s['total']} correctness={s['correctness']} "
              f"coverage={s['coverage']} efficiency={s['efficiency']}")

    if output.get("score_detail", {}) and output["score_detail"].get("per_claim"):
        print("Claims:")
        for cs in output["score_detail"]["per_claim"]:
            match_str = cs.get("matched_family_id", "none") or "unmatched"
            print(f"  {cs['claim_id']}: score={cs['score']} "
                  f"verdict={cs['verdict']} match={match_str}")

    # Show what the solver actually claimed (from conversation)
    for msg in output.get("conversation", []):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if tc.get("name") == "submit_claims" and tc.get("claims_summary"):
                    print("\nSolver claims:")
                    for c in tc["claims_summary"]:
                        print(f"  [{c['id']}] {c['text']}")
                        print(f"    vars: {c['vars']} tags: {c['tags']}")

    print(f"\nSalience families ({len(output.get('salience_families', []))}):")
    for f in output.get("salience_families", []):
        focus_str = ", ".join(f.get("focus", []))
        print(f"  {f['pattern']}: [{focus_str}] -> {f['brief_target']} "
              f"({f['n_atoms']} atoms)")


def main():
    parser = argparse.ArgumentParser(description="OI Pilot Batch Runner")
    parser.add_argument("--runs", type=int, default=2, help="Runs per world")
    parser.add_argument("--world", type=str, default=None,
                        help="Single world to run (ecosystem/treatment/education)")
    parser.add_argument("--out", type=str, default="experiments/oi_pilots",
                        help="Output directory")
    args = parser.parse_args()

    # Validate env
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL")
    compiler_model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    solver_model = os.environ.get("AZURE_SOLVER_MODEL", "gpt-5.2-codex")

    if not base_url or not api_key:
        print("ERROR: Missing AZURE_FOUNDRY_BASE_URL or AZURE_INFERENCE_CREDENTIAL")
        sys.exit(1)

    print(f"Compiler model: {compiler_model}")
    print(f"Solver model: {solver_model}")
    print(f"Base URL: {base_url[:50]}...")

    client = OpenAI(base_url=base_url, api_key=api_key)

    # Select worlds
    world_names = [args.world] if args.world else list(WORLDS.keys())

    # Output dir
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_results = []
    for world_name in world_names:
        for run_id in range(args.runs):
            try:
                result = run_single_pilot(
                    world_name, run_id, client, solver_model, compiler_model,
                )
                all_results.append(result)
            except Exception as e:
                print(f"\nERROR in {world_name} run {run_id}: {e}")
                import traceback
                traceback.print_exc()
                all_results.append({
                    "world": world_name,
                    "run_id": run_id,
                    "error": str(e),
                })

            # Save incrementally
            out_file = out_dir / f"oi_pilots_{timestamp}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)

    # Final summary
    print(f"\n{'='*70}")
    print(f"  BATCH COMPLETE: {len(all_results)} runs")
    print(f"  Results: {out_file}")
    print(f"{'='*70}")

    _print_batch_summary(all_results)


def _print_batch_summary(results: list[dict]) -> None:
    """Print aggregate summary across all runs."""
    print("\n--- BATCH SUMMARY ---\n")
    print(f"{'World':<15} {'Run':<5} {'Score':<8} {'Correct':<10} "
          f"{'Coverage':<10} {'Claims':<8} {'Steps':<6} {'Time':<6}")
    print("-" * 70)
    for r in results:
        if "error" in r:
            print(f"{r['world']:<15} {r['run_id']:<5} ERROR: {r['error'][:40]}")
            continue
        s = r.get("score", {}) or {}
        n_claims = len(r.get("claims", []))
        print(f"{r['world']:<15} {r['run_id']:<5} "
              f"{s.get('total', '-'):<8} {s.get('correctness', '-'):<10} "
              f"{s.get('coverage', '-'):<10} {n_claims:<8} "
              f"{r['n_steps']:<6} {r['elapsed_seconds']:<6}")


if __name__ == "__main__":
    main()
