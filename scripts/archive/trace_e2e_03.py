#!/usr/bin/env python
"""Trace e2e_03 epistemic claims through the full IR pipeline.

Shows: what the LLM compiler extracts, what truth values the verifier
returns, and the compatibility matrix against all sub-questions.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from sreg.models.open_investigation import ClaimCard, SubQuestionIntent
from sreg.models.scm_spec import SCMSpec
from sreg.tools.oi_compiler import CompilerOutput, build_world_summary
from sreg.tools.oi_extraction import compile_episode_claims, ExtractionContext
from sreg.tools.scm_world_gen import SCMWorldGenTool


def main():
    with open("experiments/e2e_03_epistemic/src.json") as f:
        src = json.load(f)
    with open("experiments/e2e_03_epistemic/oi_result.json") as f:
        result = json.load(f)

    # Get last submit_claims
    claims_raw = []
    for tc in result.get("solver_tool_calls", []):
        if tc.get("name") == "submit_claims":
            claims_raw = tc["args"]["claims"]

    # Reconstruct world
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
    target = src["problem"].get("target") or src["problem"].get("target_node")
    summary = build_world_summary(world, target, n_mc=20_000, seed=42)

    # Build claim cards
    claim_cards = []
    for rc in claims_raw:
        claim_cards.append(ClaimCard(
            claim_id=rc["claim_id"],
            claim_text=rc["claim_text"],
            focus_variables=rc.get("focus_variables", [])[:8],
            confidence=rc.get("confidence", 0.5),
            evidence_basis=rc.get("evidence_basis", [
                {"artifact_id": "x", "rationale": "x"}
            ]),
        ))

    # Build extraction context
    variable_descriptions = {}
    for name in summary.observable_names:
        meta = world.variable_meta.get(name)
        if not meta or not (meta.description or meta.unit):
            continue
        desc = meta.description.rstrip(".") if meta.description else ""
        if meta.unit:
            desc = f"{desc} [unit: {meta.unit}]" if desc else f"unit: {meta.unit}"
        variable_descriptions[name] = desc

    sqs_raw = src.get("sub_questions", [])
    sqs = [SubQuestionIntent(**sq) for sq in sqs_raw]
    ctx = ExtractionContext(
        research_brief=src["problem"].get("research_question", ""),
        domain=src["problem"].get("domain", ""),
        description=src["problem"].get("description", ""),
        title=src["problem"].get("title", ""),
        variable_descriptions=variable_descriptions,
        sub_questions=[
            {"sq_id": sq.sq_id, "pattern": sq.pattern,
             "text_gloss": sq.text_gloss or sq.sq_id}
            for sq in sqs
        ],
    )

    # Setup LLM
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )
    model_name = os.environ.get("AZURE_MODEL", "gpt-5.4")

    def llm_call(messages):
        instructions = messages[0]["content"] if messages else ""
        input_items = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:]
        ]
        resp = client.responses.create(
            model=model_name, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    # Compile
    compiled = compile_episode_claims(
        claim_cards, summary, llm_call=llm_call, context=ctx,
    )

    print("=== CLAIMS SUBMITTED ===")
    for rc in claims_raw:
        print(f"\n{rc['claim_id']}: {rc['claim_text'][:150]}...")
        print(f"  focus_vars: {rc['focus_variables']}")

    print("\n=== COMPILATION RESULTS ===")
    for co in compiled:
        if not isinstance(co, CompilerOutput):
            print(f"Non-CompilerOutput: {co}")
            continue
        print(f"\n--- {co.claim_id} ---")
        print(f"  compiled: {co.compiled}")
        print(f"  n_units: {len(co.units)}")
        for i, unit in enumerate(co.units):
            intent = unit.intent
            d = {
                "pattern": str(intent.pattern),
                "treatment": intent.treatment,
                "outcome": intent.outcome,
                "direction": str(intent.direction),
                "evidence_type": intent.evidence_type,
            }
            if intent.mediator:
                d["mediator"] = intent.mediator
            if intent.modifier:
                d["modifier"] = intent.modifier
            if intent.confounder:
                d["confounder"] = intent.confounder
            if intent.ranking_vars:
                d["ranking_vars"] = intent.ranking_vars
            if intent.conditioning_set:
                d["conditioning_set"] = list(intent.conditioning_set)
            print(f"  Unit {i}: {json.dumps(d, indent=4)}")
            print(f"    n_specs: {len(unit.specs)}")

    # Verify truth values
    from sreg.tools.oi_verifier import verify_atom
    from sreg.solver.scm_solver import SCMSolver

    solver = SCMSolver(world, n_mc=20_000)

    unit_details = []
    claim_tuples = []
    for co in compiled:
        if not isinstance(co, CompilerOutput) or not co.compiled:
            continue
        for unit in co.units:
            if unit.specs:
                verdicts = [
                    verify_atom(s, world, solver, 20_000, 42) for s in unit.specs
                ]
                truth = 1.0 if all(
                    v.solver_assertion_holds for v in verdicts
                ) else 0.0
            else:
                truth = 0.0
            claim_tuples.append((unit.intent, truth))
            unit_details.append((co.claim_id, unit.intent, truth))

    print("\n=== TRUTH VALUES ===")
    for cid, intent, truth in unit_details:
        print(
            f"  {cid}: pattern={intent.pattern}, "
            f"treat={intent.treatment}, out={intent.outcome}, "
            f"dir={intent.direction}, truth={truth}"
        )

    # Compatibility matrix
    from sreg.tools.oi_subquestions import (
        ClaimRepr, derive_family, derive_operator,
        structural_compatibility, resolve_all,
        score_episode_with_subquestions,
    )

    print("\n=== COMPATIBILITY MATRIX ===")
    for cid, intent, truth in unit_details:
        extra = set()
        if intent.mediator:
            extra.add(intent.mediator)
        if intent.modifier:
            extra.add(intent.modifier)
        if intent.confounder:
            extra.add(intent.confounder)
        rvars = frozenset(intent.ranking_vars) if intent.ranking_vars else frozenset()
        cr = ClaimRepr(
            family=derive_family(intent.pattern),
            operator=derive_operator(intent.pattern, intent.evidence_type),
            treatment=intent.treatment,
            outcome=intent.outcome,
            extra_roles=frozenset(extra),
            ranking_vars=rvars,
        )

        for sq in sqs:
            sq_extra = set()
            if sq.roles.mediator:
                sq_extra.add(sq.roles.mediator)
            if sq.roles.modifier:
                sq_extra.add(sq.roles.modifier)
            if sq.roles.confounder:
                sq_extra.add(sq.roles.confounder)
            sq_rvars = frozenset(sq.roles.ranking_vars) if sq.roles.ranking_vars else frozenset()
            sq_cr = ClaimRepr(
                family=derive_family(sq.pattern),
                operator=derive_operator(sq.pattern, "interventional"),
                treatment=sq.roles.treatment or "",
                outcome=sq.roles.outcome or "",
                extra_roles=frozenset(sq_extra),
                ranking_vars=sq_rvars,
            )

            compat = structural_compatibility(cr, sq_cr)
            print(
                f"  {cid} vs {sq.sq_id} ({sq.pattern}): "
                f"compat={compat:.3f}"
            )

    # Score
    resolved = resolve_all(sqs, world, target=target, n_mc=20_000, seed=42)
    score = score_episode_with_subquestions(claim_tuples, resolved)
    print(f"\n=== FINAL SCORE ===")
    print(f"  total={score.total:.3f}, cov={score.weighted_coverage:.3f}, "
          f"corr={score.correctness:.3f}, novel={score.novel_bonus:.3f}")
    for sq_score in score.sq_scores:
        sq_info = next((s for s in sqs if s.sq_id == sq_score.sq_id), None)
        marker = "[+]" if sq_score.satisfaction > 0 else "[-]"
        match_info = f" <- {sq_score.best_claim_id}" if sq_score.best_claim_id else ""
        print(
            f"  {marker} {sq_score.sq_id} ({sq_info.tier.value if sq_info else '?'}): "
            f"sat={sq_score.satisfaction:.3f}{match_info}"
        )


if __name__ == "__main__":
    main()
