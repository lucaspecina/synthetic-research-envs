"""OI No-Data Baseline Probe: measure investigation gap.

Gives the solver the brief + variable names but NO data.
If the solver still scores well, the environment isn't forcing investigation.

Usage:
    python scripts/oi_nodata_baseline.py [--runs N] [--world NAME]

Key metric: investigation_gap = score_with_data - score_no_data
If gap is small, the world is shortcutteable from priors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

from sreg.models.open_investigation import (
    AskOperator,
    ClaimCard,
    SQRoles,
    SQTier,
    SubQuestionIntent,
)
from sreg.models.research_problem import DataAsset, ResearchProblem
from sreg.tools.oi_runner import OIEpisodeRunner

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "tools"))
from test_oi_curated_worlds import (
    world_ecosystem,
    world_education,
    world_treatment,
    world_treatment_simpson,
)

N_MC = 20_000
SEED = 42

# Re-use same briefs and SQs from oi_pilot_batch
WORLDS = {
    "ecosystem": {
        "factory": world_ecosystem,
        "target": "Fish",
        "brief": (
            "A marine research station collected observational data on fish "
            "populations across 300 sites. Variables include sunlight exposure, "
            "water temperature, depth, nutrient concentration, and algae density.\n\n"
            "Your task: Investigate the factors that drive fish population "
            "variation across sites. What are the main determinants? Are there "
            "interaction effects or confounding relationships?"
        ),
        "variables": ["Sun", "Temp", "Depth", "Nutrients", "Algae", "Fish"],
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
        "variables": ["Age", "Severity", "Treatment", "Biomarker", "Recovery"],
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
        "variables": [
            "Wealth", "Motivation", "Education", "Skill", "Income",
        ],
    },
    "treatment_simpson": {
        "factory": world_treatment_simpson,
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
        "variables": ["Age", "Severity", "Treatment", "Biomarker", "Recovery"],
    },
}

# Same SQs as oi_pilot_batch (for consistent comparison)
WORLD_SQS = {
    "ecosystem": [
        SubQuestionIntent(
            sq_id="sq1", pattern="observational_association",
            roles=SQRoles(treatment="Algae", outcome="Fish"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq2", pattern="observational_association",
            roles=SQRoles(treatment="Depth", outcome="Fish"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq3", pattern="confounding",
            roles=SQRoles(treatment="Nutrients", outcome="Fish",
                          confounder="Sun"),
            ask=AskOperator.EXISTENCE, tier=SQTier.MEDIUM,
        ),
        SubQuestionIntent(
            sq_id="sq4", pattern="heterogeneity",
            roles=SQRoles(treatment="Nutrients", outcome="Algae",
                          modifier="Temp"),
            ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
        ),
    ],
    "treatment": [
        SubQuestionIntent(
            sq_id="sq1", pattern="causal_effect",
            roles=SQRoles(treatment="Treatment", outcome="Recovery"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq2", pattern="mediation",
            roles=SQRoles(treatment="Treatment", outcome="Recovery",
                          mediator="Biomarker"),
            ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq3", pattern="confounding",
            roles=SQRoles(treatment="Treatment", outcome="Recovery",
                          confounder="Severity"),
            ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq4", pattern="causal_effect",
            roles=SQRoles(treatment="Severity", outcome="Recovery"),
            ask=AskOperator.SIGN, tier=SQTier.MEDIUM,
        ),
    ],
    "education": [
        SubQuestionIntent(
            sq_id="sq1", pattern="causal_effect",
            roles=SQRoles(treatment="Education", outcome="Income"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq2", pattern="mediation",
            roles=SQRoles(treatment="Education", outcome="Income",
                          mediator="Skill"),
            ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
        ),
        SubQuestionIntent(
            sq_id="sq3", pattern="causal_effect",
            roles=SQRoles(treatment="Wealth", outcome="Income"),
            ask=AskOperator.SIGN, tier=SQTier.MEDIUM,
        ),
        SubQuestionIntent(
            sq_id="sq4", pattern="causal_effect",
            roles=SQRoles(treatment="Motivation", outcome="Income"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.LOW,
        ),
    ],
    # treatment_simpson: SQs designed to detect Simpson's paradox
    # SQ1 asks about the CRUDE association (should be NEGATIVE — data-indexed!)
    # SQ2 asks about the CAUSAL effect (should be POSITIVE)
    # A no-data LLM would guess both are positive → fails SQ1
    "treatment_simpson": [
        SubQuestionIntent(
            sq_id="sq1", pattern="observational_association",
            roles=SQRoles(treatment="Treatment", outcome="Recovery"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
            text_gloss="Is Treatment associated with Recovery? (crude direction is data-indexed)",
        ),
        SubQuestionIntent(
            sq_id="sq2", pattern="causal_effect",
            roles=SQRoles(treatment="Treatment", outcome="Recovery"),
            ask=AskOperator.EXISTENCE_AND_SIGN, tier=SQTier.HIGH,
            text_gloss="Does Treatment causally help Recovery? (after adjusting)",
        ),
        SubQuestionIntent(
            sq_id="sq3", pattern="confounding",
            roles=SQRoles(treatment="Treatment", outcome="Recovery",
                          confounder="Severity"),
            ask=AskOperator.EXISTENCE, tier=SQTier.HIGH,
            text_gloss="Does Severity confound the Treatment-Recovery relationship?",
        ),
        SubQuestionIntent(
            sq_id="sq4", pattern="causal_effect",
            roles=SQRoles(treatment="Severity", outcome="Recovery"),
            ask=AskOperator.SIGN, tier=SQTier.MEDIUM,
            text_gloss="Does Severity negatively affect Recovery?",
        ),
    ],
}

# No-data prompt: give brief + variable names, ask for claims
NODATA_SYSTEM = """You are a research scientist. You have been given a research brief
and the names of the variables in the dataset. However, you DO NOT have access
to the actual data. Based on your domain knowledge and the information provided,
produce your best research findings as structured claim cards.

IMPORTANT:
- You have NO data to analyze. Make claims based on domain knowledge only.
- Be honest about your confidence level.
- Report 3-5 claims covering the key questions in the brief.
- Use the variable names provided exactly as given.

Respond with a JSON object: {"claims": [...]} where each claim has:
- claim_id: unique ID (C1, C2, ...)
- claim_text: what you found (natural language)
- focus_variables: list of variable names involved
- confidence: 0.0-1.0
- evidence_basis: [{"artifact_id": "prior_knowledge", "rationale": "..."}]
- pattern_tags: optional list of tags (association, causal_effect, mediation, etc.)
"""


def run_nodata_probe(
    world_name: str,
    run_id: int,
    client: OpenAI,
    model: str,
    compiler_model: str,
) -> dict:
    """Run no-data baseline for a single world."""
    cfg = WORLDS[world_name]
    world = cfg["factory"]()
    variables = cfg["variables"]
    brief = cfg["brief"]

    # Build user prompt with brief + variable names (NO data)
    user_prompt = (
        f"## Research Brief\n\n{brief}\n\n"
        f"## Available Variables\n\n"
        f"The dataset contains these variables: {', '.join(variables)}\n\n"
        f"## Your Task\n\n"
        f"Based on the brief and variable names above, produce 3-5 research "
        f"findings as claim cards. Remember: you have NO actual data."
    )

    # Call LLM for claims (single-shot, no tools)
    try:
        response = client.responses.create(
            model=model,
            instructions=NODATA_SYSTEM,
            input=user_prompt,
        )
        text = ""
        for item in response.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        text += part.text
    except Exception as e:
        print(f"  LLM call failed: {e}")
        return {"error": str(e)}

    # Parse claims from JSON response
    claims = _parse_claims_from_text(text)
    if not claims:
        print(f"  No claims parsed from response")
        return {"error": "no_claims", "raw_response": text[:500]}

    # Create problem (with data — needed for scoring, but solver didn't see it)
    df = world.sample(300, seed=SEED)
    asset = DataAsset(
        artifact_id="dataset_main", name="main_study",
        description="Observational study data", format="tabular",
        data=df.to_dict("records"), columns=list(df.columns), num_rows=300,
    )
    problem = ResearchProblem(
        world_id=world.id, title=f"No-data probe: {world.id}",
        description=brief, domain="research", data_assets=[asset],
        available_actions=[], budget=10,
        research_question=brief, target_node=cfg["target"],
        target_states=["low", "medium", "high"],
    )

    # Create compiler
    compiler_client = OpenAI(
        base_url=os.environ.get("AZURE_FOUNDRY_BASE_URL", ""),
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )

    def llm_compiler(messages):
        instructions = messages[0]["content"] if messages else ""
        input_items = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:]
        ]
        resp = compiler_client.responses.create(
            model=compiler_model, instructions=instructions, input=input_items,
        )
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        return part.text
        return ""

    # Score the no-data claims through the full pipeline
    runner = OIEpisodeRunner(
        problem, world, seed=SEED + run_id, n_mc=N_MC, llm_call=llm_compiler,
    )
    if world_name in WORLD_SQS:
        runner.set_subquestions(WORLD_SQS[world_name])

    # Submit claims to runner
    runner.submit_claims(claims)

    # Get scores
    v2_score = runner.get_score()
    sq_score = runner.get_sq_score()

    result = {
        "world": world_name,
        "run": run_id,
        "mode": "no_data",
        "n_claims": len(claims),
        "claims": [
            {"id": c.claim_id, "text": c.claim_text[:200],
             "vars": c.focus_variables}
            for c in claims
        ],
    }
    if v2_score:
        result["v2"] = {
            "total": round(v2_score.total, 3),
            "correctness": round(v2_score.correctness, 3),
            "coverage": round(v2_score.coverage, 3),
        }
    if sq_score:
        result["sq"] = {
            "total": round(sq_score.total, 3),
            "wcov": round(sq_score.weighted_coverage, 3),
            "correct": round(sq_score.correctness, 3),
            "novel": round(sq_score.novel_bonus, 3),
        }

    return result


def _parse_claims_from_text(text: str) -> list[ClaimCard]:
    """Parse ClaimCards from LLM JSON response."""
    # Try to find JSON in the response
    import re
    json_match = re.search(r'\{[\s\S]*"claims"[\s\S]*\}', text)
    if not json_match:
        return []

    try:
        data = json.loads(json_match.group())
        raw_claims = data.get("claims", [])
    except json.JSONDecodeError:
        return []

    cards = []
    for raw in raw_claims:
        try:
            card = ClaimCard(
                claim_id=raw.get("claim_id", f"C{len(cards)+1}"),
                claim_text=raw.get("claim_text", ""),
                focus_variables=raw.get("focus_variables", []),
                confidence=raw.get("confidence", 0.5),
                evidence_basis=raw.get("evidence_basis", [
                    {"artifact_id": "prior_knowledge",
                     "rationale": "domain knowledge"}
                ]),
                pattern_tags=raw.get("pattern_tags", []),
            )
            cards.append(card)
        except Exception:
            continue
    return cards


def main():
    parser = argparse.ArgumentParser(description="OI No-Data Baseline Probe")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--world", type=str, default=None,
                        help="Single world name, or all if omitted")
    args = parser.parse_args()

    solver_model = os.environ.get(
        "AZURE_SOLVER_MODEL",
        os.environ.get("AZURE_MODEL", "gpt-5.2-codex"),
    )
    compiler_model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")

    client = OpenAI(
        base_url=base_url,
        api_key=os.environ.get("AZURE_INFERENCE_CREDENTIAL", ""),
    )

    print(f"No-data baseline probe")
    print(f"Solver: {solver_model} | Compiler: {compiler_model}")
    print(f"Base URL: {base_url[:50]}...")

    worlds = [args.world] if args.world else list(WORLDS.keys())
    all_results = []

    for world_name in worlds:
        for run_id in range(args.runs):
            print(f"\n--- {world_name} run {run_id} (no data) ---")
            t0 = time.time()
            result = run_nodata_probe(
                world_name, run_id, client, solver_model, compiler_model,
            )
            elapsed = time.time() - t0
            result["elapsed"] = round(elapsed, 1)
            all_results.append(result)

            # Print summary
            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                n = result["n_claims"]
                print(f"  Claims: {n} | Time: {elapsed:.0f}s")
                for c in result["claims"]:
                    print(f"    [{c['id']}] {c['text'][:100]}")
                if "v2" in result:
                    v2 = result["v2"]
                    print(f"  v2: total={v2['total']} correct={v2['correctness']}")
                if "sq" in result:
                    sq = result["sq"]
                    print(
                        f"  SQ: total={sq['total']} wcov={sq['wcov']} "
                        f"correct={sq['correct']} novel={sq['novel']}"
                    )

    # Batch summary
    print(f"\n{'='*70}")
    print(f"  NO-DATA BASELINE SUMMARY")
    print(f"{'='*70}")
    print(f"\n{'World':<15} {'Run':>4} {'Claims':>6} "
          f"{'v2 Total':>9} {'v2 Corr':>8} "
          f"{'SQ Total':>9} {'SQ WCov':>8} {'SQ Corr':>8}")
    print("-" * 80)
    for r in all_results:
        if "error" in r:
            print(f"{r['world']:<15} {r['run']:>4} {'ERR':>6}")
            continue
        v2t = r.get("v2", {}).get("total", 0)
        v2c = r.get("v2", {}).get("correctness", 0)
        sqt = r.get("sq", {}).get("total", 0)
        sqw = r.get("sq", {}).get("wcov", 0)
        sqc = r.get("sq", {}).get("correct", 0)
        print(
            f"{r['world']:<15} {r['run']:>4} {r['n_claims']:>6} "
            f"{v2t:>9.3f} {v2c:>8.3f} "
            f"{sqt:>9.3f} {sqw:>8.3f} {sqc:>8.3f}"
        )

    # Save results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"experiments/oi_dual_scoring/nodata_baseline_{ts}.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
