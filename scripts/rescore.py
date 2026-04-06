#!/usr/bin/env python
"""Controlled rescore: re-evaluate frozen cases without regenerating worlds.

Re-runs parts of the scoring pipeline on existing E2E results, isolating
the effect of code changes from worldgen/solver variance.

Modes:
    --recompile   Re-compile claims + re-verify + re-judge + re-aggregate (default)
    --rejudge     Use frozen compiled specs + truths, re-judge relevance + re-aggregate
    --reaggregate Use all frozen inputs, only re-compute score arithmetic

Requirements:
    - src.json must have `sub_questions_v2` (grounded SQs with verdicts)
    - oi_result.json must have `score_inputs_v2` (claims, compiled, truths, relevance)
    - Runs generated BEFORE persistence was added are best-effort only

Usage:
    python scripts/rescore.py results/e2e_batch_bug8_9_fix/missing_data/
    python scripts/rescore.py results/e2e_batch_bug8_9_fix/*/ --rejudge
    python scripts/rescore.py results/e2e_batch_bug8_9_fix/*/ --reaggregate
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
load_dotenv()

# ASCII-safe output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Load frozen context
# ---------------------------------------------------------------------------

def load_frozen(exp_dir: Path) -> dict:
    """Load frozen case data from src.json + oi_result.json."""
    src_path = exp_dir / "src.json"
    result_path = exp_dir / "oi_result.json"

    if not src_path.exists() or not result_path.exists():
        raise FileNotFoundError(f"Missing src.json or oi_result.json in {exp_dir}")

    with open(src_path, encoding="utf-8") as f:
        src = json.load(f)
    with open(result_path, encoding="utf-8") as f:
        result = json.load(f)

    return {"src": src, "result": result, "dir": exp_dir}


def reconstruct_world(src: dict):
    """Reconstruct SCMWorld from scm_construct args in src.json."""
    from sreg.models.scm_spec import SCMSpec
    from sreg.tools.scm_world_gen import SCMWorldGenTool

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
    if scm_args is None:
        raise ValueError("No scm_construct call found in src.json")

    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    return gen.generate(spec, seed=42)


def load_claims(result: dict) -> list:
    """Load claims from score_inputs_v2 or fallback to tool call trace."""
    from sreg.models.open_investigation import ClaimCard

    # Prefer score_inputs_v2 (new format)
    si = result.get("score_inputs_v2", {})
    if si.get("claims"):
        return [ClaimCard(**c) for c in si["claims"]]

    # Fallback: extract from solver tool calls
    raw_claims = []
    for tc in result.get("solver_tool_calls", []):
        if tc.get("name") == "submit_claims":
            raw_claims = tc["args"]["claims"]

    claims = []
    for rc in raw_claims:
        claims.append(ClaimCard(
            claim_id=rc["claim_id"],
            claim_text=rc["claim_text"],
            focus_variables=rc.get("focus_variables", [])[:8],
            confidence=rc.get("confidence", 0.5),
            evidence_basis=rc.get("evidence_basis"),
        ))
    return claims


def load_sqs_v2(src: dict, world):
    """Load grounded SQs v2 from src.json."""
    from sreg.models.open_investigation import SubQuestionIntentV2

    raw = src.get("sub_questions_v2", [])
    if not raw:
        return None
    return [SubQuestionIntentV2(**sq) for sq in raw]


def make_llm_call():
    """Build dual-protocol LLM call (works for both compiler and judge).

    The compiler v1 fallback calls llm_call(messages), while the judge
    and grammar-direct compiler call llm_call(system, user). This wrapper
    handles both protocols transparently.
    """
    from openai import OpenAI

    client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")

    def _call_api(instructions: str, input_items: list) -> str:
        resp = client.responses.create(
            model=model, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    def llm_call(*args):
        if len(args) == 2:
            # (system, user) protocol — judge + grammar-direct compiler
            system, user = args
            return _call_api(system, [{"role": "user", "content": user}])
        elif len(args) == 1 and isinstance(args[0], list):
            # messages protocol — v1 fallback compiler
            messages = args[0]
            instructions = messages[0]["content"] if messages else ""
            input_items = [
                {"role": m["role"], "content": m["content"]}
                for m in messages[1:]
            ]
            return _call_api(instructions, input_items)
        else:
            raise TypeError(f"llm_call: unexpected args {[type(a) for a in args]}")

    return llm_call


# ---------------------------------------------------------------------------
# Rescore modes
# ---------------------------------------------------------------------------

def rescore_recompile(exp_dir: Path) -> dict:
    """Re-compile + re-verify + re-judge + re-aggregate."""
    frozen = load_frozen(exp_dir)
    src, result = frozen["src"], frozen["result"]

    world = reconstruct_world(src)
    claims = load_claims(result)
    sqs_v2 = load_sqs_v2(src, world)

    if not claims:
        return {"experiment": str(exp_dir), "error": "No claims found"}
    if not sqs_v2:
        return {"experiment": str(exp_dir), "error": "No sub_questions_v2 in src.json"}

    # Get runner config
    si = result.get("score_inputs_v2", {})
    config = si.get("runner_config", {"seed": 42, "n_mc": 20_000})

    # Build problem for runner
    from sreg.models.research_problem import ResearchProblem
    problem = ResearchProblem(**src["problem"])

    # Build runner
    from sreg.tools.oi_runner import OIEpisodeRunner
    llm = make_llm_call()
    runner = OIEpisodeRunner(
        problem, world,
        seed=config["seed"], n_mc=config["n_mc"], llm_call=llm,
    )
    runner.set_subquestions_v2(sqs_v2)

    # Reconstruct trace (for evidence_basis validation)
    if si.get("trace"):
        from sreg.models.open_investigation import EpisodeTrace
        runner.trace = EpisodeTrace(**si["trace"])
    else:
        # Best-effort: register all data_assets as accessed
        for da in problem.data_assets:
            from sreg.models.open_investigation import ArtifactAccess
            runner.trace.accesses.append(
                ArtifactAccess(artifact_id=da.artifact_id, step=0)
            )

    # Compile claims
    from sreg.tools.oi_compiler import build_world_summary
    from sreg.tools.oi_extraction import compile_episode_claims

    target = src["problem"].get("target_node", world.variables[-1])
    summary = build_world_summary(world, target, n_mc=config["n_mc"], seed=config["seed"])
    ctx = runner._build_extraction_context(summary.observable_names)
    compiled = compile_episode_claims(claims, summary, llm_call=llm, context=ctx)

    # Submit (triggers scoring via _score_with_judge)
    runner._submitted = True
    runner._last_compiled = compiled
    runner._last_claims = list(claims)

    # Run v2 scoring
    score = runner._score_with_judge(claims, compiled)

    return _build_report(exp_dir, claims, compiled, score, result)


def rescore_rejudge(exp_dir: Path) -> dict:
    """Use frozen compiled specs + truths, re-judge relevance."""
    frozen = load_frozen(exp_dir)
    src, result = frozen["src"], frozen["result"]
    si = result.get("score_inputs_v2", {})

    if not si:
        return {"experiment": str(exp_dir), "error": "No score_inputs_v2 in oi_result.json"}

    world = reconstruct_world(src)
    claims = load_claims(result)
    sqs_v2 = load_sqs_v2(src, world)

    if not sqs_v2:
        return {"experiment": str(exp_dir), "error": "No sub_questions_v2 in src.json"}

    claim_truths = si["claim_truths"]

    # Use frozen judge_claims (preserves exact specs_summary from original run)
    judge_claims = si.get("judge_claims")
    if not judge_claims:
        return {"experiment": str(exp_dir), "error": "No judge_claims in score_inputs_v2"}

    # Build judge SQ inputs from grounded SQs
    judge_sqs = _build_judge_sqs(sqs_v2)

    # Run LLM judge
    from sreg.tools.oi_relevance_judge import judge_all_claims
    llm = make_llm_call()

    brief = src.get("problem", {}).get("research_question", "")
    relevance_results = judge_all_claims(
        claims=judge_claims, sqs=judge_sqs,
        brief_text=brief, llm_call=llm,
    )

    # Re-aggregate
    score = _aggregate_score(sqs_v2, claims, claim_truths, relevance_results)
    return _build_report_from_score(exp_dir, score, result)


def rescore_reaggregate(exp_dir: Path) -> dict:
    """Use all frozen inputs, only re-compute score arithmetic."""
    frozen = load_frozen(exp_dir)
    src, result = frozen["src"], frozen["result"]
    si = result.get("score_inputs_v2", {})

    if not si:
        return {"experiment": str(exp_dir), "error": "No score_inputs_v2 in oi_result.json"}

    world = reconstruct_world(src)
    claims = load_claims(result)
    sqs_v2 = load_sqs_v2(src, world)

    if not sqs_v2:
        return {"experiment": str(exp_dir), "error": "No sub_questions_v2 in src.json"}

    claim_truths = si["claim_truths"]
    relevance_results = si["relevance_results"]

    score = _aggregate_score(sqs_v2, claims, claim_truths, relevance_results)
    return _build_report_from_score(exp_dir, score, result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_judge_sqs(sqs_v2) -> list[dict]:
    """Build judge SQ inputs from grounded SubQuestionIntentV2 list."""
    from sreg.tools.oi_sq_compiler import render_answer_key

    judge_sqs = []
    for sq in sqs_v2:
        answer_keys = []
        for vs in sq.verification_specs:
            if vs.verdict:
                ak = render_answer_key(vs.verdict)
                ak["role"] = vs.role
                answer_keys.append(ak)
        judge_sqs.append({
            "sq_id": sq.sq_id,
            "text_gloss": sq.text_gloss,
            "focus_variables": list(sq.focus_variables),
            "tier": sq.tier.value,
            "answer_keys": answer_keys,
        })
    return judge_sqs


def _aggregate_score(sqs_v2, claims, claim_truths: dict, relevance_results: list):
    """Re-compute score from frozen truths and relevance."""
    from sreg.models.open_investigation import EpisodeSubQuestionScore, SubQuestionScore

    rel_map = {}
    for r in relevance_results:
        rel_map[(r["claim_id"], r["sq_id"])] = r["relevance"]

    sq_scores = []
    total_weight = 0.0
    weighted_sat_sum = 0.0

    for sq in sqs_v2:
        best_score = 0.0
        best_claim_id = None

        for claim in claims:
            cid = claim.claim_id
            truth = claim_truths.get(cid, 0.0)
            rel = rel_map.get((cid, sq.sq_id), 0.0)
            s = truth * rel
            if s > best_score:
                best_score = s
                best_claim_id = cid

        satisfaction = min(1.0, best_score)
        sq_scores.append(SubQuestionScore(
            sq_id=sq.sq_id,
            satisfaction=satisfaction,
            best_claim_id=best_claim_id,
            matched=best_score > 0.0,
        ))

        w = sq.weight
        total_weight += w
        weighted_sat_sum += w * satisfaction

    all_truths = [claim_truths.get(c.claim_id, 0.0) for c in claims]
    weighted_coverage = weighted_sat_sum / total_weight if total_weight > 0 else 0.0
    correctness = sum(all_truths) / len(all_truths) if all_truths else 0.0
    total = min(1.0, correctness * weighted_coverage)

    return EpisodeSubQuestionScore(
        sq_scores=sq_scores,
        coverage=sum(1 for s in sq_scores if s.matched) / len(sq_scores) if sq_scores else 0.0,
        weighted_coverage=weighted_coverage,
        correctness=correctness,
        novel_bonus=0.0,
        total=total,
    )


def _build_report(exp_dir, claims, compiled, score, original_result) -> dict:
    """Build comparison report."""
    from sreg.tools.oi_compiler import CompilerOutput

    n_compiled = sum(
        1 for co in compiled
        if isinstance(co, CompilerOutput) and co.compiled
    )

    return {
        "experiment": exp_dir.name,
        "n_claims": len(claims),
        "n_compiled": n_compiled,
        "score": {
            "total": round(score.total, 4),
            "correctness": round(score.correctness, 4),
            "coverage": round(score.weighted_coverage, 4),
        },
        "original_score": {
            "total": round(original_result["score"]["total"], 4),
            "correctness": round(original_result["score"]["correctness"], 4),
            "coverage": round(original_result["score"]["weighted_coverage"], 4),
        },
        "delta": round(score.total - original_result["score"]["total"], 4),
        "sq_details": [
            {
                "sq_id": s.sq_id,
                "satisfaction": round(s.satisfaction, 3),
                "matched_by": s.best_claim_id,
            }
            for s in score.sq_scores
        ],
    }


def _build_report_from_score(exp_dir, score, original_result) -> dict:
    """Build comparison report (without compiled details)."""
    return {
        "experiment": exp_dir.name,
        "score": {
            "total": round(score.total, 4),
            "correctness": round(score.correctness, 4),
            "coverage": round(score.weighted_coverage, 4),
        },
        "original_score": {
            "total": round(original_result["score"]["total"], 4),
            "correctness": round(original_result["score"]["correctness"], 4),
            "coverage": round(original_result["score"]["weighted_coverage"], 4),
        },
        "delta": round(score.total - original_result["score"]["total"], 4),
        "sq_details": [
            {
                "sq_id": s.sq_id,
                "satisfaction": round(s.satisfaction, 3),
                "matched_by": s.best_claim_id,
            }
            for s in score.sq_scores
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Controlled rescore: re-evaluate frozen cases"
    )
    parser.add_argument("experiments", nargs="+", help="Experiment directories")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--recompile", action="store_true",
                       help="Re-compile + re-verify + re-judge (default)")
    group.add_argument("--rejudge", action="store_true",
                       help="Use frozen specs/truths, re-judge relevance")
    group.add_argument("--reaggregate", action="store_true",
                       help="Use all frozen inputs, only re-compute arithmetic")
    args = parser.parse_args()

    # Determine mode
    if args.reaggregate:
        mode = "reaggregate"
    elif args.rejudge:
        mode = "rejudge"
    else:
        mode = "recompile"

    print(f"Mode: {mode}")
    print()

    results = []
    for exp_path in args.experiments:
        exp_dir = Path(exp_path)
        if not exp_dir.is_dir():
            continue

        print(f"{'='*60}")
        print(f"  {exp_dir.name}")
        print(f"{'='*60}")

        try:
            if mode == "reaggregate":
                r = rescore_reaggregate(exp_dir)
            elif mode == "rejudge":
                r = rescore_rejudge(exp_dir)
            else:
                r = rescore_recompile(exp_dir)
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            continue

        if "error" in r:
            print(f"  {r['error']}")
            continue

        s = r["score"]
        o = r["original_score"]
        d = r["delta"]
        arrow = "+" if d > 0 else ""
        print(f"  Original: {o['total']:.4f} (corr={o['correctness']:.3f} cov={o['coverage']:.3f})")
        print(f"  Rescore:  {s['total']:.4f} (corr={s['correctness']:.3f} cov={s['coverage']:.3f})")
        print(f"  Delta:    {arrow}{d:.4f}")
        print()

        for sq in r["sq_details"]:
            marker = "[+]" if sq["satisfaction"] > 0 else "[-]"
            match = f" <- {sq['matched_by']}" if sq["matched_by"] else ""
            print(f"    {marker} {sq['sq_id']}: sat={sq['satisfaction']:.3f}{match}")

        print()
        results.append(r)

    # Summary
    if len(results) > 1:
        print(f"\n{'='*60}")
        print(f"  SUMMARY ({len(results)} cases)")
        print(f"{'='*60}")
        print(f"  {'Case':<20} {'Original':>8} {'Rescore':>8} {'Delta':>8}")
        print(f"  {'-'*50}")
        for r in results:
            name = r["experiment"][:20]
            o = r["original_score"]["total"]
            s = r["score"]["total"]
            d = r["delta"]
            arrow = "+" if d > 0 else ""
            print(f"  {name:<20} {o:>8.4f} {s:>8.4f} {arrow}{d:>7.4f}")

        avg_orig = sum(r["original_score"]["total"] for r in results) / len(results)
        avg_new = sum(r["score"]["total"] for r in results) / len(results)
        avg_delta = avg_new - avg_orig
        arrow = "+" if avg_delta > 0 else ""
        print(f"  {'-'*50}")
        print(f"  {'AVERAGE':<20} {avg_orig:>8.4f} {avg_new:>8.4f} {arrow}{avg_delta:>7.4f}")


if __name__ == "__main__":
    main()
