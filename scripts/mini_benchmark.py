#!/usr/bin/env python3
"""Mini benchmark: 3-5 real SRCs via orchestrator + agent + teacher.

Purpose: get a real baseline before designing the full benchmark infrastructure.
This is NOT the final benchmark runner — it's a learning tool.

Usage:
    python scripts/mini_benchmark.py [--cases N] [--output DIR]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.agent.agent import AgentSolver
from sreg.harness.agent_trajectory import extract_agent_trajectory
from sreg.harness.comparison import compare_trajectories
from sreg.harness.trajectory import generate_teacher_trajectory
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_check import WorldCheckTool

# ---------------------------------------------------------------------------
# Goals — varied domains for the mini experiment
# ---------------------------------------------------------------------------

GOALS = [
    (
        "Generate a research problem about marine ecology in a fictional "
        "archipelago. Use dag_construct with 8 nodes. Design a research case "
        "with at least 3 different evaluation types. Medium difficulty."
    ),
    (
        "Generate a research problem about epidemiology, studying the spread "
        "of a fictional disease in a remote region. Use dag_construct with 10 "
        "nodes. Design a research case with causal and diagnostic questions."
    ),
    (
        "Generate a research problem about materials science, investigating "
        "why a new alloy fails under certain conditions. Use dag_construct "
        "with 8 nodes. Include causal effect and best intervention questions."
    ),
    (
        "Generate a research problem about agricultural productivity on a "
        "fictional planet. Use dag_construct with 10 nodes. Design a case "
        "with inference, causal, and comparison questions."
    ),
    (
        "Generate a research problem about geological processes in a "
        "fictional volcanic island chain. Use dag_construct with 8 nodes. "
        "Design a research case with diagnostic and causal questions."
    ),
]

# ---------------------------------------------------------------------------
# Single case runner
# ---------------------------------------------------------------------------


def run_single_case(
    goal: str, case_id: int, seed: int, output_dir: Path
) -> dict:
    """Run one case: orchestrator -> agent -> teacher -> compare.

    Returns a dict with all metrics for this case.
    """
    result_data = {
        "case_id": case_id,
        "goal": goal,
        "seed": seed,
        "timestamp": datetime.now().isoformat(),
    }

    # --- Phase 1: Orchestrator generates SRC ---
    print(f"\n{'='*70}")
    print(f"CASE {case_id}: Orchestrator generating SRC...")
    print(f"  Goal: {goal[:80]}...")
    print(f"  Seed: {seed}")

    t0 = time.time()
    try:
        orchestrator = Orchestrator()
        orch_result = orchestrator.run(goal)
    except Exception as e:
        print(f"  ORCHESTRATOR FAILED: {e}")
        result_data["orchestrator_completed"] = False
        result_data["orchestrator_error"] = str(e)[:200]
        return result_data

    orch_time = time.time() - t0
    result_data["orchestrator_time_s"] = round(orch_time, 1)
    result_data["orchestrator_attempts"] = orch_result.attempts

    if not orch_result.world or not orch_result.problem:
        print(f"  ORCHESTRATOR INCOMPLETE: world={bool(orch_result.world)}, "
              f"problem={bool(orch_result.problem)}")
        result_data["orchestrator_completed"] = False
        return result_data

    result_data["orchestrator_completed"] = True
    world = orch_result.world
    problem = orch_result.problem

    print(f"  OK in {orch_time:.1f}s, {orch_result.attempts} attempt(s)")
    print(f"  Title: {world.scenario_title or '(no title)'}")
    print(f"  Nodes: {len(world.nodes)}, Edges: {len(world.edges)}")
    print(f"  Target: {problem.target_node}")
    print(f"  Budget: {problem.budget}")
    print(f"  Actions: {len(problem.available_actions)}")

    # Save SRC
    src_data = {
        "world": world.model_dump(mode="json"),
        "problem": problem.model_dump(mode="json"),
    }
    if orch_result.task:
        src_data["tasks"] = [t.model_dump(mode="json") for t in orch_result.task]
    if hasattr(orch_result, "case_plan") and orch_result.case_plan:
        src_data["case_plan"] = orch_result.case_plan.model_dump(mode="json")

    case_dir = output_dir / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)
    src_path = case_dir / f"case_{case_id:03d}_src.json"
    src_path.write_text(json.dumps(src_data, indent=2, default=str), encoding="utf-8")

    # --- Structural metrics ---
    checker = WorldCheckTool()
    check_result = checker.check(world)
    result_data["worldcheck_passed"] = check_result.passed
    result_data["num_nodes"] = len(world.nodes)
    result_data["num_edges"] = len(world.edges)
    result_data["scenario_title"] = world.scenario_title or ""

    # CasePlan info
    tasks = orch_result.task or []
    result_data["num_tasks"] = len(tasks)
    result_data["eval_types"] = list(set(t.type.value for t in tasks))
    result_data["num_eval_types"] = len(result_data["eval_types"])

    print(f"  WorldCheck: {'PASS' if check_result.passed else 'FAIL'}")
    print(f"  Tasks: {len(tasks)} ({', '.join(result_data['eval_types'])})")

    # --- Phase 2: Teacher solver + Random baseline ---
    print(f"  Running teacher...")
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)
    true_target = true_state[problem.target_node]
    result_data["true_target_state"] = true_target

    # Random baseline (independent of teacher)
    uniform = {s: 1.0 / len(problem.target_states) for s in problem.target_states}
    true_posterior = solver.posterior(problem.target_node, {})
    verifier = VerifierTool()
    random_score = verifier.score(
        agent_posterior=uniform,
        true_posterior=true_posterior,
        budget_used=0,
        budget_total=problem.budget,
    )
    result_data["random_kl"] = random_score.functional_score
    print(f"  Random baseline KL: {random_score.functional_score:.4f}")

    teacher_traj = None
    try:
        teacher_traj = generate_teacher_trajectory(world, problem, seed=seed)
        teacher_kl = 0.0  # teacher is exact
        result_data["teacher_kl"] = teacher_kl
        result_data["teacher_steps"] = len(teacher_traj.steps)
        print(f"  Teacher: {len(teacher_traj.steps)} steps, KL=0.0")
    except Exception as e:
        print(f"  TEACHER FAILED: {e}")
        result_data["teacher_error"] = str(e)[:200]

    # --- Phase 3: Agent solver ---
    print(f"  Running agent...")
    t0 = time.time()
    try:
        agent = AgentSolver(max_iterations=15)
        agent_result = agent.solve(world, problem, seed=seed)
        agent_time = time.time() - t0
        result_data["agent_time_s"] = round(agent_time, 1)

        if agent_result.submitted_answer:
            result_data["agent_submitted"] = True
            result_data["agent_kl"] = agent_result.score.functional_score
            result_data["agent_budget_used"] = agent_result.budget_used
            result_data["agent_budget_total"] = agent_result.budget_total
            result_data["agent_observations"] = len(agent_result.observations)
            result_data["agent_answer"] = agent_result.submitted_answer

            # Compare with random
            result_data["agent_beats_random"] = (
                agent_result.score.functional_score < random_score.functional_score
            )

            print(f"  Agent: submitted, KL={agent_result.score.functional_score:.4f}, "
                  f"budget={agent_result.budget_used}/{agent_result.budget_total}, "
                  f"{'BEATS' if result_data['agent_beats_random'] else 'LOSES TO'} random")
        else:
            result_data["agent_submitted"] = False
            result_data["agent_budget_used"] = agent_result.budget_used
            result_data["agent_observations"] = len(agent_result.observations)
            print(f"  Agent: NO SUBMIT, {len(agent_result.observations)} observations")

        # Extract trajectory
        agent_traj = extract_agent_trajectory(
            agent_result, problem, world_id=world.id, seed=seed,
        )

        # Compare with teacher
        if teacher_traj:
            comparison = compare_trajectories(teacher_traj, agent_traj)
            result_data["verdict"] = comparison.verdict
            print(f"  Verdict: {comparison.verdict}")

            # Save trajectory + comparison
            traj_data = {
                "agent_trajectory": agent_traj.model_dump(mode="json"),
                "comparison": comparison.model_dump(mode="json"),
            }
            traj_path = case_dir / f"case_{case_id:03d}_result.json"
            traj_path.write_text(
                json.dumps(traj_data, indent=2, default=str), encoding="utf-8"
            )

    except Exception as e:
        agent_time = time.time() - t0
        result_data["agent_time_s"] = round(agent_time, 1)
        result_data["agent_error"] = str(e)[:200]
        print(f"  AGENT FAILED: {e}")

    return result_data


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------


def print_summary(results: list[dict]) -> str:
    """Print and return aggregate summary."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("MINI BENCHMARK SUMMARY")
    lines.append("=" * 70)

    total = len(results)
    completed = sum(1 for r in results if r.get("orchestrator_completed"))
    submitted = sum(1 for r in results if r.get("agent_submitted"))
    beats_random = sum(1 for r in results if r.get("agent_beats_random"))

    lines.append(f"  Total cases:          {total}")
    lines.append(f"  Orchestrator complete: {completed}/{total} "
                 f"({completed/total*100:.0f}%)")
    lines.append(f"  Agent submitted:      {submitted}/{total} "
                 f"({submitted/total*100:.0f}%)")
    lines.append(f"  Agent beats random:   {beats_random}/{total} "
                 f"({beats_random/total*100:.0f}%)")

    # KL stats
    agent_kls = [r["agent_kl"] for r in results if "agent_kl" in r]
    if agent_kls:
        import numpy as np
        lines.append("")
        lines.append(f"  Agent KL:  mean={np.mean(agent_kls):.4f}, "
                     f"median={np.median(agent_kls):.4f}, "
                     f"min={min(agent_kls):.4f}, max={max(agent_kls):.4f}")

    random_kls = [r["random_kl"] for r in results if "random_kl" in r]
    if random_kls:
        lines.append(f"  Random KL: mean={np.mean(random_kls):.4f}")

    # Verdicts
    verdicts = [r.get("verdict", "N/A") for r in results]
    verdict_counts = {}
    for v in verdicts:
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    lines.append("")
    lines.append("  Verdicts:")
    for v, c in sorted(verdict_counts.items()):
        lines.append(f"    {v}: {c}")

    # Eval types seen
    all_types = set()
    for r in results:
        all_types.update(r.get("eval_types", []))
    lines.append("")
    lines.append(f"  Eval types seen: {sorted(all_types)}")

    # Per-case table
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"  {'ID':>3} {'Orch':>5} {'WC':>4} {'Sub':>4} {'AgKL':>7} "
                 f"{'RdKL':>7} {'Verdict':>10} {'Types':>3} {'Title'}")
    lines.append("-" * 70)
    for r in results:
        case_id = r.get("case_id", "?")
        orch = "OK" if r.get("orchestrator_completed") else "FAIL"
        wc = "PASS" if r.get("worldcheck_passed") else "FAIL" if "worldcheck_passed" in r else "-"
        sub = "YES" if r.get("agent_submitted") else "NO" if "agent_submitted" in r else "-"
        akl = f"{r['agent_kl']:.4f}" if "agent_kl" in r else "-"
        rkl = f"{r['random_kl']:.4f}" if "random_kl" in r else "-"
        verdict = r.get("verdict", "-")
        ntypes = r.get("num_eval_types", 0)
        title = r.get("scenario_title", "")[:25]
        lines.append(f"  {case_id:>3} {orch:>5} {wc:>4} {sub:>4} {akl:>7} "
                     f"{rkl:>7} {verdict:>10} {ntypes:>3} {title}")

    # Failure modes
    lines.append("")
    lines.append("FAILURE MODES:")
    modes = []
    for r in results:
        if not r.get("orchestrator_completed"):
            modes.append(("ORCH_FAIL", r.get("case_id")))
        elif not r.get("agent_submitted"):
            modes.append(("NO_SUBMIT", r.get("case_id")))
        elif r.get("agent_kl", 0) > 2.0:
            modes.append(("HIGH_KL", r.get("case_id")))
        elif not r.get("agent_beats_random"):
            modes.append(("WORSE_THAN_RANDOM", r.get("case_id")))
        elif r.get("agent_observations", 0) == 0:
            modes.append(("NO_OBSERVATIONS", r.get("case_id")))

    if modes:
        mode_counts = {}
        for m, _ in modes:
            mode_counts[m] = mode_counts.get(m, 0) + 1
        for m, c in sorted(mode_counts.items(), key=lambda x: -x[1]):
            cases = [str(cid) for mo, cid in modes if mo == m]
            lines.append(f"  {m}: {c} (cases: {', '.join(cases)})")
    else:
        lines.append("  None detected")

    lines.append("=" * 70)

    text = "\n".join(lines)
    print(text)
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Mini benchmark: real SRCs")
    parser.add_argument("--cases", type=int, default=3, help="Number of cases (max 5)")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: experiments/mini_TIMESTAMP)"
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sreg.agent.agent").setLevel(logging.WARNING)
    logging.getLogger("sreg.orchestrator.orchestrator").setLevel(logging.WARNING)

    n_cases = min(args.cases, len(GOALS))

    # Output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("experiments") / f"mini_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Mini Benchmark: {n_cases} cases")
    print(f"Output: {output_dir}")
    print(f"Seed: {args.seed}")

    # Run cases
    results = []
    for i in range(n_cases):
        goal = GOALS[i]
        seed = args.seed + i
        result = run_single_case(goal, case_id=i + 1, seed=seed, output_dir=output_dir)
        results.append(result)

    # Summary
    summary_text = print_summary(results)

    # Save results
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )

    report_path = output_dir / "report.txt"
    report_path.write_text(summary_text, encoding="utf-8")

    # Save config
    config = {
        "n_cases": n_cases,
        "seed": args.seed,
        "goals": GOALS[:n_cases],
        "timestamp": datetime.now().isoformat(),
    }
    config_path = output_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()
