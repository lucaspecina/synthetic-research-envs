#!/usr/bin/env python3
"""Run the SREG benchmark: real SRCs via orchestrator, agent on all tasks.

This is Level 2 QA — periodic product quality evaluation.
The benchmark is PARTIAL and EVOLVING.

Usage:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --cases 5 --output experiments/bench_001
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
from sreg.harness.benchmark import (
    BenchmarkRunner,
    format_benchmark_report,
    save_benchmark,
)

# ---------------------------------------------------------------------------
# Goals — varied domains, diverse eval types
# ---------------------------------------------------------------------------

GOALS = [
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
]


def main():
    parser = argparse.ArgumentParser(description="SREG Benchmark Runner")
    parser.add_argument(
        "--cases", type=int, default=3,
        help="Number of SRCs to generate (max 5)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: experiments/bench_TIMESTAMP)",
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
        output_dir = Path("experiments") / f"bench_{ts}"

    print(f"SREG Benchmark: {n_cases} SRCs")
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
            print(
                f"    {tr.task_type:<25} {tr.verdict:<10} "
                f"score={score_str} obs={tr.budget_used}{fm}"
            )

    agent = AgentSolver(max_iterations=15)
    runner = BenchmarkRunner(agent=agent)
    report = runner.run(goals, seed=args.seed, on_src=on_src)

    # Print and save
    text = format_benchmark_report(report)
    print(text)

    save_benchmark(report, output_dir)
    print(f"\nResults saved to: {output_dir}/")


if __name__ == "__main__":
    main()
