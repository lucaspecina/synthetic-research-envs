#!/usr/bin/env python
"""Rescore an existing experiment with the current compiler.

Takes claims + SQs from a previous E2E run and re-compiles + re-scores
WITHOUT regenerating the world or re-running the solver. This is the
fast path for iterating on compiler/matching changes.

Usage:
    python scripts/rescore.py experiments/e2e_03_epistemic/
    python scripts/rescore.py experiments/e2e_02_*/ experiments/e2e_03_*/
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()


def load_experiment(exp_dir: Path) -> dict:
    """Load world, claims, and SQs from an experiment directory."""
    src_path = exp_dir / "src.json"
    result_path = exp_dir / "oi_result.json"

    if not src_path.exists() or not result_path.exists():
        raise FileNotFoundError(f"Missing src.json or oi_result.json in {exp_dir}")

    with open(src_path) as f:
        src = json.load(f)
    with open(result_path) as f:
        result = json.load(f)

    return {"src": src, "result": result, "dir": exp_dir}


def extract_claims_from_trace(result: dict) -> list[dict]:
    """Extract submitted claims from the solver tool call trace.

    Takes the LAST submit_claims call (earlier ones may have failed validation).
    """
    claims = []
    for tc in result.get("solver_tool_calls", []):
        if tc.get("name") == "submit_claims":
            claims = tc["args"]["claims"]
    return claims


def rescore(exp_dir: Path, use_llm: bool = True) -> dict:
    """Re-compile and re-score an experiment."""
    from sreg.models.open_investigation import ClaimCard, SubQuestionIntent
    from sreg.tools.oi_compiler import build_world_summary, CompilerOutput
    from sreg.tools.oi_extraction import compile_episode_claims
    from sreg.tools.oi_subquestions import (
        resolve_all,
        score_episode_with_subquestions,
    )
    from sreg.tools.oi_verifier import verify_atom
    from sreg.solver.scm_solver import SCMSolver
    from sreg.world.scm import SCMWorld
    from sreg.tools.scm_world_gen import SCMWorldGenTool
    from sreg.models.scm_spec import SCMSpec

    exp = load_experiment(exp_dir)
    src = exp["src"]
    result = exp["result"]

    # --- Reconstruct world from the scm_construct tool call ---
    scm_args = None
    for tc in src.get("process", {}).get("tools_called", []):
        if tc.get("tool") == "scm_construct":
            res = tc.get("result", {})
            # Successful calls have world_id; failed ones have error
            if "world_id" in res or "error" not in res:
                scm_args = tc["args"]
                break
    if scm_args is None:
        # Fallback: take last scm_construct (most likely the retry that worked)
        for tc in src.get("process", {}).get("tools_called", []):
            if tc.get("tool") == "scm_construct":
                scm_args = tc["args"]
    if scm_args is None:
        raise ValueError("No scm_construct call found in src.json")

    # Edges are serialized as {"from": ..., "to": ...} dicts — convert to tuples
    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [
            (e["from"], e["to"]) for e in scm_args["edges"]
        ]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    world = gen.generate(spec, seed=42)

    # --- Get claims ---
    raw_claims = extract_claims_from_trace(result)
    if not raw_claims:
        return {
            "experiment": str(exp_dir),
            "submitted": False,
            "error": "No claims found in trace",
        }

    claims = []
    for rc in raw_claims:
        claims.append(ClaimCard(
            claim_id=rc["claim_id"],
            claim_text=rc["claim_text"],
            focus_variables=rc.get("focus_variables", [])[:8],
            confidence=rc.get("confidence", 0.5),
            evidence_basis=rc.get("evidence_basis", [
                {"artifact_id": "dataset_bg", "rationale": "Analysis from solver investigation"}
            ]),
        ))

    # --- Get SQs ---
    raw_sqs = src.get("sub_questions", [])
    if not raw_sqs:
        return {
            "experiment": str(exp_dir),
            "submitted": True,
            "error": "No sub-questions in src.json",
        }
    sqs = [SubQuestionIntent(**sq) for sq in raw_sqs]

    # --- Build compiler LLM (optional) ---
    llm_call = None
    if use_llm:
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
                api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
            )
            model = os.environ.get("AZURE_MODEL", "gpt-5.4")

            def llm_call(messages):
                instructions = messages[0]["content"] if messages else ""
                input_items = [
                    {"role": m["role"], "content": m["content"]}
                    for m in messages[1:]
                ]
                resp = client.responses.create(
                    model=model, instructions=instructions, input=input_items,
                )
                for item in resp.output:
                    if item.type == "message":
                        for part in item.content:
                            if hasattr(part, "text"):
                                return part.text
                return ""
        except Exception as e:
            print(f"  LLM setup failed ({e}), using deterministic compiler")
            llm_call = None

    # --- Compile claims ---
    target = src["problem"].get("target") or src["problem"].get("target_node")
    summary = build_world_summary(world, target, n_mc=20_000, seed=42)

    # Build extraction context from src.json
    from sreg.tools.oi_extraction import ExtractionContext
    ctx = ExtractionContext(
        research_brief=src.get("problem", {}).get("research_question", ""),
        domain=src.get("problem", {}).get("domain", ""),
        description=src.get("problem", {}).get("description", ""),
        title=src.get("problem", {}).get("title", ""),
        sub_questions=[
            {"sq_id": sq.sq_id, "pattern": sq.pattern,
             "text_gloss": sq.text_gloss or sq.sq_id}
            for sq in sqs
        ],
    )
    compiled = compile_episode_claims(claims, summary, llm_call=llm_call, context=ctx)

    # --- Resolve SQs ---
    resolved = resolve_all(sqs, world, target=target, n_mc=20_000, seed=42)

    # --- Score ---
    solver = SCMSolver(world, n_mc=20_000)
    claim_tuples = []
    for co in compiled:
        if not isinstance(co, CompilerOutput) or not co.compiled:
            continue
        for unit in co.units:
            if unit.specs:
                verdicts = [
                    verify_atom(s, world, solver, 20_000, 42)
                    for s in unit.specs
                ]
                truth = 1.0 if all(v.solver_assertion_holds for v in verdicts) else 0.0
            else:
                truth = 0.0
            claim_tuples.append((unit.intent, truth))

    score = score_episode_with_subquestions(claim_tuples, resolved)

    # --- Report ---
    # Build SQ lookup for question text and tier
    sq_lookup = {sq.sq_id: sq for sq in sqs}
    sq_details = []
    for sq_score in score.sq_scores:
        sq_info = sq_lookup.get(sq_score.sq_id)
        sq_details.append({
            "sq_id": sq_score.sq_id,
            "question": sq_info.text_gloss or sq_info.sq_id if sq_info else "?",
            "tier": sq_info.tier.value if sq_info else "?",
            "hit": sq_score.satisfaction > 0,
            "satisfaction": round(sq_score.satisfaction, 3),
            "matched_by": sq_score.best_claim_id,
        })

    return {
        "experiment": str(exp_dir),
        "submitted": True,
        "n_claims": len(claims),
        "n_compiled_units": len(claim_tuples),
        "n_sqs": len(sqs),
        "score": {
            "total": round(score.total, 3),
            "coverage": round(score.weighted_coverage, 3),
            "correctness": round(score.correctness, 3),
            "novel_bonus": round(score.novel_bonus, 3),
        },
        "sqs": sq_details,
        "original_score": result.get("score"),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rescore experiments with current compiler")
    parser.add_argument("experiments", nargs="+", help="Experiment directories")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic compiler")
    args = parser.parse_args()

    for exp_path in args.experiments:
        exp_dir = Path(exp_path)
        if not exp_dir.is_dir():
            print(f"Skipping {exp_path} (not a directory)")
            continue

        print(f"\n{'='*60}")
        print(f"Rescoring: {exp_dir.name}")
        print(f"{'='*60}")

        try:
            result = rescore(exp_dir, use_llm=not args.no_llm)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if not result["submitted"]:
            print(f"  {result.get('error', 'No submission')}")
            continue

        s = result["score"]
        print(f"  Claims: {result['n_claims']} -> {result['n_compiled_units']} units")
        print(f"  SQs: {result['n_sqs']}")
        print(f"  Score: {s['total']} (cov={s['coverage']} corr={s['correctness']} novel={s['novel_bonus']})")
        print()

        hits = sum(1 for sq in result["sqs"] if sq["hit"])
        print(f"  SQ Results: {hits}/{result['n_sqs']} hits")
        for sq in result["sqs"]:
            marker = "[+]" if sq["hit"] else "[-]"
            match_info = f" <- {sq['matched_by']}" if sq["matched_by"] else ""
            print(f"    {marker} {sq['sq_id']} ({sq['tier']}): sat={sq['satisfaction']}{match_info}")


if __name__ == "__main__":
    main()
