#!/usr/bin/env python3
"""Run the SREG environment diagnostic: real SRCs via orchestrator, agent on all tasks.

This is Level 2 QA — periodic environment quality validation.
The diagnostic is PARTIAL and EVOLVING.

NOTE: This is NOT the real benchmark of SREG. The real benchmark is the
transfer experiment (BEFORE -> TRAIN on SREG -> AFTER on external benchmarks).
See research/synthesis/benchmark_analysis.md. This diagnostic validates that the generator
produces quality environments.

Usage:
    python scripts/run_diagnostic.py
    python scripts/run_diagnostic.py --cases 5 --output experiments/diag_001
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.agent.agent import AgentSolver
from sreg.harness.diagnostic import (
    DiagnosticRunner,
    format_diagnostic_report,
    save_diagnostic,
)

# ---------------------------------------------------------------------------
# Goals — varied domains, diverse eval types
# ---------------------------------------------------------------------------

GOALS = [
    # --- Original 5 ---
    (
        "Generate a research problem about marine ecology in a fictional "
        "archipelago. Use dag_construct with 8 nodes. Design a research case "
        "with at least 4 different evaluation types including causal_effect "
        "and hypothesis_selection. Medium difficulty."
    ),
    (
        "Generate a research problem about epidemiology, studying the spread "
        "of a fictional disease in a remote region. Use dag_construct with 10 "
        "nodes. Design a research case with infer_target, compare_interventions, "
        "and should_condition questions."
    ),
    (
        "Generate a research problem about materials science, investigating "
        "why a new alloy fails under certain conditions. Use dag_construct "
        "with 8 nodes. Include causal_effect, best_intervention, and "
        "adjustment_set questions."
    ),
    (
        "Generate a research problem about agricultural productivity on a "
        "fictional planet. Use dag_construct with 10 nodes. Design a case "
        "with infer_target, next_best_observation, infer_latent_cause, "
        "and hypothesis_selection."
    ),
    (
        "Generate a research problem about geological processes in a "
        "fictional volcanic island chain. Use dag_construct with 8 nodes. "
        "Design a research case with at least 4 evaluation types including "
        "compare_interventions and best_intervention."
    ),
    # --- New 10 for broader coverage ---
    (
        "Generate a research problem about urban air quality in a fictional "
        "megacity. Use dag_construct with 10 nodes. Design a research case "
        "with infer_target, causal_effect, should_condition, and "
        "hypothesis_selection."
    ),
    (
        "Generate a research problem about deep-sea hydrothermal vents on a "
        "fictional ocean moon. Use dag_construct with 8 nodes. Design a case "
        "with infer_latent_cause, next_best_observation, compare_interventions, "
        "and adjustment_set."
    ),
    (
        "Generate a research problem about soil microbiome dynamics in a "
        "fictional terraforming project. Use dag_construct with 10 nodes. "
        "Include infer_target, best_intervention, should_condition, and "
        "causal_effect questions."
    ),
    (
        "Generate a research problem about cognitive development in a "
        "fictional education system. Use dag_construct with 8 nodes. Design "
        "a case with hypothesis_selection, compare_interventions, "
        "next_best_observation, and infer_target."
    ),
    (
        "Generate a research problem about freshwater ecosystem collapse "
        "in a fictional lake district. Use dag_construct with 10 nodes. "
        "Include causal_effect, adjustment_set, infer_latent_cause, and "
        "best_intervention."
    ),
    (
        "Generate a research problem about stellar formation in a fictional "
        "nebula. Use dag_construct with 8 nodes. Design a case with "
        "infer_target, hypothesis_selection, should_condition, and "
        "compare_interventions."
    ),
    (
        "Generate a research problem about antibiotic resistance in a "
        "fictional hospital network. Use dag_construct with 10 nodes. "
        "Include next_best_observation, causal_effect, best_intervention, "
        "and infer_target."
    ),
    (
        "Generate a research problem about climate adaptation in a fictional "
        "coastal community. Use dag_construct with 8 nodes. Design a case "
        "with adjustment_set, compare_interventions, hypothesis_selection, "
        "and infer_latent_cause."
    ),
    (
        "Generate a research problem about neural plasticity in a fictional "
        "species. Use dag_construct with 10 nodes. Include infer_target, "
        "should_condition, next_best_observation, and causal_effect."
    ),
    (
        "Generate a research problem about volcanic soil fertility on a "
        "fictional island. Use dag_construct with 8 nodes. Design a case "
        "with best_intervention, hypothesis_selection, infer_target, and "
        "compare_interventions."
    ),
]


def main():
    parser = argparse.ArgumentParser(description="SREG Environment Diagnostic")
    parser.add_argument(
        "--cases", type=int, default=15,
        help="Number of SRCs to generate (max 15)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: experiments/diag_TIMESTAMP)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    else:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("sreg.agent.agent").setLevel(logging.WARNING)
        logging.getLogger("sreg.orchestrator.orchestrator").setLevel(logging.WARNING)

    n_cases = min(args.cases, len(GOALS))
    goals = GOALS[:n_cases]

    if args.output:
        output_dir = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("experiments") / f"diag_{ts}"

    print(f"SREG Diagnostic: {n_cases} SRCs")
    print(f"Output: {output_dir}")
    print(f"Seed: {args.seed}")

    def on_src(case_id, src_result):
        status = "OK" if src_result.orchestrator_completed else "FAIL"
        n_tasks = len(src_result.task_results)
        n_sub = sum(1 for tr in src_result.task_results if tr.submitted)
        types = ", ".join(sorted(src_result.eval_types))
        print(
            f"\n  SRC {case_id}: {status} | "
            f"{n_tasks} tasks ({n_sub} submitted) | {types}"
        )
        for tr in src_result.task_results:
            fm = f" [{tr.failure_mode}]" if tr.failure_mode else ""
            score_str = f"{tr.score:.4f}" if tr.score is not None else "N/A"
            base_str = ""
            if tr.baseline_score is not None and tr.agent_beats_baseline is not None:
                beat = ">" if tr.agent_beats_baseline else "<="
                base_str = f" (vs random {tr.baseline_score:.4f} {beat})"
            print(
                f"    {tr.task_type:<25} {tr.verdict:<10} "
                f"score={score_str} obs={tr.budget_used}{fm}{base_str}"
            )

    agent = AgentSolver(max_iterations=15)
    runner = DiagnosticRunner(agent=agent)
    report = runner.run(goals, seed=args.seed, on_src=on_src)

    # Print and save
    text = format_diagnostic_report(report)
    print(text)

    save_diagnostic(report, output_dir)
    print(f"\nResults saved to: {output_dir}/")


if __name__ == "__main__":
    main()
