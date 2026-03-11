#!/usr/bin/env python3
"""Run a diagnostic batch: generate N cases, run agent + teacher, save trajectories.

This is NOT a test or benchmark. It's a diagnostic tool to inspect how the
agent interacts with the environment and identify failure modes.

Usage:
    python scripts/diagnostic_batch.py --output output/diagnostic_001
    python scripts/diagnostic_batch.py --output output/diagnostic_001 --cases 10
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.agent.agent import AgentSolver
from sreg.harness.agent_trajectory import extract_agent_trajectory
from sreg.harness.comparison import compare_trajectories
from sreg.harness.trajectory import generate_teacher_trajectory
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


# -- Case configurations --
# Varied: templates, seeds, nodes, edge_strength, budget
CASE_CONFIGS = [
    # latent_preference - 6 nodes (small)
    {"seed": 1, "template": "latent_preference", "nodes": 6, "es": 0.7, "budget": 3},
    {"seed": 2, "template": "latent_preference", "nodes": 6, "es": 0.5, "budget": 3},
    {"seed": 3, "template": "latent_preference", "nodes": 6, "es": 0.9, "budget": 4},
    # latent_preference - 8 nodes
    {"seed": 10, "template": "latent_preference", "nodes": 8, "es": 0.7, "budget": 4},
    {"seed": 11, "template": "latent_preference", "nodes": 8, "es": 0.5, "budget": 5},
    # latent_preference - 10 nodes (sweet spot)
    {"seed": 20, "template": "latent_preference", "nodes": 10, "es": 0.6, "budget": 5},
    {"seed": 21, "template": "latent_preference", "nodes": 10, "es": 0.7, "budget": 6},
    {"seed": 22, "template": "latent_preference", "nodes": 10, "es": 0.5, "budget": 5},
    # causal_chain - various sizes
    {"seed": 30, "template": "causal_chain", "nodes": 6, "es": 0.7, "budget": 3},
    {"seed": 31, "template": "causal_chain", "nodes": 6, "es": 0.5, "budget": 3},
    {"seed": 32, "template": "causal_chain", "nodes": 8, "es": 0.7, "budget": 4},
    {"seed": 33, "template": "causal_chain", "nodes": 8, "es": 0.5, "budget": 5},
    {"seed": 34, "template": "causal_chain", "nodes": 10, "es": 0.6, "budget": 5},
    # fork_collider - various sizes
    {"seed": 40, "template": "fork_collider", "nodes": 6, "es": 0.7, "budget": 3},
    {"seed": 41, "template": "fork_collider", "nodes": 6, "es": 0.5, "budget": 3},
    {"seed": 42, "template": "fork_collider", "nodes": 8, "es": 0.7, "budget": 4},
    {"seed": 43, "template": "fork_collider", "nodes": 8, "es": 0.5, "budget": 5},
    {"seed": 44, "template": "fork_collider", "nodes": 10, "es": 0.6, "budget": 5},
    # Edge cases: tight budget, generous budget
    {"seed": 50, "template": "latent_preference", "nodes": 6, "es": 0.7, "budget": 1},
    {"seed": 51, "template": "latent_preference", "nodes": 6, "es": 0.7, "budget": 5},
    {"seed": 52, "template": "causal_chain", "nodes": 10, "es": 0.7, "budget": 3},
    {"seed": 53, "template": "fork_collider", "nodes": 10, "es": 0.7, "budget": 8},
    # High edge_strength (easy signal) vs low (noisy)
    {"seed": 60, "template": "latent_preference", "nodes": 8, "es": 0.3, "budget": 4},
    {"seed": 61, "template": "latent_preference", "nodes": 8, "es": 0.9, "budget": 4},
    {"seed": 62, "template": "causal_chain", "nodes": 8, "es": 0.3, "budget": 4},
]


def run_single_case(
    config: dict, agent: AgentSolver, case_num: int, total: int
) -> dict:
    """Run a single case and return results dict."""
    label = "case_%02d" % case_num
    tpl = config["template"]
    seed = config["seed"]
    nodes = config["nodes"]
    es = config["es"]
    budget = config["budget"]

    print(
        "\n--- [%d/%d] %s: %s seed=%d nodes=%d es=%.1f budget=%d ---"
        % (case_num, total, label, tpl, seed, nodes, es, budget)
    )

    result = {
        "case": label,
        "config": config,
        "status": "unknown",
        "error": None,
        "world_id": None,
        "agent_kl": None,
        "teacher_kl": None,
        "agent_budget_used": None,
        "teacher_budget_used": None,
        "verdict": None,
        "agent_submitted": False,
        "num_agent_steps": 0,
        "num_agent_errors": 0,
        "agent_trajectory": None,
        "comparison": None,
    }

    try:
        # Generate world
        gen = WorldGenTool()
        world = gen.generate(
            WorldGenConfig(
                seed=seed,
                num_nodes=nodes,
                edge_strength=es,
                template_family=tpl,
            )
        )
        result["world_id"] = world.id

        # Build problem
        builder = ProblemBuilder()
        problem = builder.build(world, budget=budget)

        print("  World: %s | Target: %s" % (world.id, problem.target_node))
        print("  Question: %s" % problem.research_question[:100])

        # Run teacher
        teacher_traj = generate_teacher_trajectory(world, problem, seed=seed)
        result["teacher_kl"] = 0.0  # teacher is optimal
        result["teacher_budget_used"] = len(teacher_traj.steps)

        # Run agent
        t0 = time.time()
        agent_result = agent.solve(world, problem, seed=seed)
        elapsed = time.time() - t0

        # Extract trajectory
        agent_traj = extract_agent_trajectory(
            agent_result, problem, world_id=world.id, seed=seed
        )
        comp = compare_trajectories(teacher_traj, agent_traj)

        result["status"] = "completed"
        result["agent_submitted"] = agent_result.submitted_answer is not None
        result["agent_kl"] = agent_traj.score
        result["agent_budget_used"] = agent_traj.budget_used
        result["verdict"] = comp.verdict
        result["num_agent_steps"] = len(agent_traj.steps)
        result["num_agent_errors"] = len(
            [s for s in agent_traj.steps if s.error is not None]
        )
        result["agent_trajectory"] = agent_traj.model_dump()
        result["comparison"] = comp.model_dump()

        # Print summary
        kl_str = "%.4f" % agent_traj.score if agent_traj.score is not None else "N/A"
        print(
            "  Agent: KL=%s budget=%d/%d verdict=%s (%.1fs)"
            % (kl_str, agent_traj.budget_used, budget, comp.verdict, elapsed)
        )
        if agent_traj.budget_used == 0 and agent_result.submitted_answer is not None:
            print("  !! Agent submitted without observing anything")
        if not agent_result.submitted_answer:
            print("  !! Agent did NOT submit an answer")
        if result["num_agent_errors"] > 0:
            print("  !! Agent had %d tool errors" % result["num_agent_errors"])

        # Show teacher vs agent action comparison
        teacher_actions = [s.action_node for s in teacher_traj.steps]
        agent_actions = [
            s.tool_args.get("variable", "?")
            for s in agent_traj.steps
            if s.tool_call == "observe" and s.tool_args
        ]
        print("  Teacher actions: %s" % teacher_actions)
        print("  Agent actions:   %s" % agent_actions)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print("  ERROR: %s" % str(e)[:200])
        traceback.print_exc()

    return result


def main():
    parser = argparse.ArgumentParser(description="Diagnostic batch run")
    parser.add_argument(
        "--output", "-o", type=str, default="output/diagnostic",
        help="Output directory for results",
    )
    parser.add_argument(
        "--cases", "-n", type=int, default=None,
        help="Limit to first N cases (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    else:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("sreg.agent.agent").setLevel(logging.WARNING)

    configs = CASE_CONFIGS[:args.cases] if args.cases else CASE_CONFIGS
    total = len(configs)

    print("=" * 70)
    print("SREG Diagnostic Batch: %d cases" % total)
    print("=" * 70)

    agent = AgentSolver(max_iterations=15)
    results = []

    for i, config in enumerate(configs, 1):
        result = run_single_case(config, agent, i, total)
        results.append(result)

    # -- Summary report --
    print("\n" + "=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)

    completed = [r for r in results if r["status"] == "completed"]
    errors = [r for r in results if r["status"] == "error"]
    submitted = [r for r in completed if r["agent_submitted"]]
    no_submit = [r for r in completed if not r["agent_submitted"]]

    print("\nOverall: %d/%d completed, %d errors" % (len(completed), total, len(errors)))
    print("Submitted: %d/%d" % (len(submitted), len(completed)))

    if submitted:
        kls = [r["agent_kl"] for r in submitted if r["agent_kl"] is not None]
        if kls:
            print("\nAgent KL distribution:")
            print("  min=%.4f  median=%.4f  max=%.4f  mean=%.4f" % (
                min(kls),
                sorted(kls)[len(kls) // 2],
                max(kls),
                sum(kls) / len(kls),
            ))

    # Verdict distribution
    verdicts = {}
    for r in completed:
        v = r["verdict"] or "UNKNOWN"
        verdicts[v] = verdicts.get(v, 0) + 1
    print("\nVerdicts:")
    for v in ["EXCELLENT", "GOOD", "FAIR", "POOR", "NO_SUBMIT", "UNKNOWN"]:
        if v in verdicts:
            print("  %s: %d" % (v, verdicts[v]))

    # Cases with errors in tool calls
    error_cases = [r for r in completed if r["num_agent_errors"] > 0]
    if error_cases:
        print("\nCases with agent tool errors: %d" % len(error_cases))
        for r in error_cases:
            print("  %s: %d errors" % (r["case"], r["num_agent_errors"]))

    # Zero-observation submissions
    zero_obs = [
        r for r in submitted
        if r["agent_budget_used"] == 0
    ]
    if zero_obs:
        print("\nZero-observation submissions (possible trivial cases): %d" % len(zero_obs))
        for r in zero_obs:
            kl = r["agent_kl"]
            kl_str = "%.4f" % kl if kl is not None else "N/A"
            print("  %s: KL=%s" % (r["case"], kl_str))

    # Save results
    from pathlib import Path

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save summary (without full trajectories)
    summary = []
    for r in results:
        s = {k: v for k, v in r.items() if k not in ("agent_trajectory", "comparison")}
        summary.append(s)

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("\nSummary saved: %s" % summary_path)

    # Save individual trajectories and comparisons
    for r in results:
        if r["agent_trajectory"]:
            traj_path = out_dir / ("%s_trajectory.json" % r["case"])
            traj_path.write_text(
                json.dumps(r["agent_trajectory"], indent=2, default=str),
                encoding="utf-8",
            )
        if r["comparison"]:
            comp_path = out_dir / ("%s_comparison.json" % r["case"])
            comp_path.write_text(
                json.dumps(r["comparison"], indent=2, default=str),
                encoding="utf-8",
            )

    print("Trajectories saved: %s/" % out_dir)
    print("\nView any trajectory:")
    print("  python scripts/view_trajectory.py %s/case_01_trajectory.json" % out_dir)
    print("  python scripts/view_trajectory.py -c %s/case_01_comparison.json" % out_dir)


if __name__ == "__main__":
    main()
