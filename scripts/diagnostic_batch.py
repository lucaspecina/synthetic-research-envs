#!/usr/bin/env python3
"""S.2 Diagnostic pipeline: run N real SRCs, agent on EACH task, per-type metrics.

Generates SRCs via the real orchestrator (LLM), then runs the agent on every
task in each SRC. Collects per-eval-type metrics and failure mode analysis.

This is the bridge between "tests pass" and "benchmark of the real product".

Usage:
    python scripts/diagnostic_batch.py
    python scripts/diagnostic_batch.py --cases 5 --output experiments/diag_001
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.agent.agent import AgentSolver
from sreg.harness.agent_trajectory import extract_agent_trajectory
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.tools.world_check import WorldCheckTool

# ---------------------------------------------------------------------------
# Goals — varied domains, explicitly requesting diverse eval types
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


# ---------------------------------------------------------------------------
# Failure mode classification
# ---------------------------------------------------------------------------

def classify_failure(task_result: dict) -> str | None:
    """Classify the failure mode for a single task result.

    Returns None if no failure detected.
    """
    if task_result.get("error"):
        return "AGENT_CRASH"
    if not task_result.get("submitted"):
        return "NO_SUBMIT"
    if task_result.get("format_errors", 0) > 0 and not task_result.get("submitted"):
        return "FORMAT_ERROR"
    score = task_result.get("score")
    if score is None:
        return "NO_SCORE"
    # For distribution types: KL > 2 is very bad; for choice: score == 0 is wrong
    task_type = task_result.get("task_type", "")
    if task_type in ("infer_target", "causal_effect", "infer_latent_cause"):
        if score > 2.0:
            return "HIGH_KL"
    else:
        if score == 0.0:
            return "WRONG_ANSWER"
    # Trivial: answered well without observing
    if task_result.get("budget_used", 0) == 0 and score is not None:
        if task_type in ("infer_target", "causal_effect", "infer_latent_cause"):
            if score < 0.5:
                return "TRIVIAL"
        else:
            if score > 0.5:
                return "TRIVIAL"
    return None


# ---------------------------------------------------------------------------
# Run agent on a single task
# ---------------------------------------------------------------------------

def run_agent_on_task(
    agent: AgentSolver,
    world,
    problem,
    task,
    seed: int,
) -> dict:
    """Run the agent on a specific task and return metrics."""
    task_result = {
        "task_id": task.id,
        "task_type": task.type.value,
        "question": task.question[:200] if task.question else "",
        "submitted": False,
        "score": None,
        "budget_used": 0,
        "num_observations": 0,
        "num_steps": 0,
        "format_errors": 0,
        "error": None,
        "answer": None,
        "time_s": 0,
        "failure_mode": None,
    }

    try:
        t0 = time.time()
        result = agent.solve(world, problem, seed=seed, task=task)
        task_result["time_s"] = round(time.time() - t0, 1)

        task_result["submitted"] = result.submitted_answer is not None
        task_result["budget_used"] = result.budget_used
        task_result["num_observations"] = len(result.observations)

        if result.score is not None:
            task_result["score"] = round(result.score.functional_score, 4)

        if result.submitted_answer is not None:
            # Serialize answer for JSON
            task_result["answer"] = result.submitted_answer

        # Count format errors from messages
        for msg in result.messages:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                try:
                    parsed = json.loads(content)
                    if "error" in parsed:
                        task_result["format_errors"] += 1
                except (json.JSONDecodeError, TypeError):
                    pass

        # Count steps (tool calls)
        for msg in result.messages:
            if msg.get("role") == "assistant":
                task_result["num_steps"] += len(msg.get("tool_calls", []))

        # Extract trajectory for saving
        traj = extract_agent_trajectory(result, problem, world_id=world.id, seed=seed)
        task_result["trajectory"] = traj.model_dump(mode="json")

    except Exception as e:
        task_result["error"] = str(e)[:300]
        task_result["time_s"] = round(time.time() - t0, 1)

    task_result["failure_mode"] = classify_failure(task_result)
    return task_result


# ---------------------------------------------------------------------------
# Run a single SRC (orchestrator + agent on all tasks)
# ---------------------------------------------------------------------------

def run_single_src(
    goal: str,
    case_id: int,
    seed: int,
    agent: AgentSolver,
) -> dict:
    """Generate one SRC via orchestrator, run agent on each task."""
    src_result = {
        "case_id": case_id,
        "goal": goal[:120],
        "seed": seed,
        "timestamp": datetime.now().isoformat(),
        "orchestrator_completed": False,
        "orchestrator_error": None,
        "orchestrator_time_s": 0,
        "worldcheck_passed": None,
        "num_nodes": 0,
        "num_edges": 0,
        "scenario_title": "",
        "num_tasks": 0,
        "eval_types": [],
        "task_results": [],
    }

    # --- Phase 1: Orchestrator ---
    print(f"\n{'='*70}")
    print(f"SRC {case_id}: Orchestrator generating...")
    print(f"  Goal: {goal[:80]}...")

    t0 = time.time()
    try:
        orchestrator = Orchestrator()
        orch_result = orchestrator.run(goal)
    except Exception as e:
        src_result["orchestrator_error"] = str(e)[:200]
        print(f"  ORCHESTRATOR FAILED: {e}")
        return src_result

    src_result["orchestrator_time_s"] = round(time.time() - t0, 1)

    if not orch_result.world or not orch_result.problem:
        src_result["orchestrator_error"] = "Incomplete result"
        print("  ORCHESTRATOR INCOMPLETE")
        return src_result

    src_result["orchestrator_completed"] = True
    world = orch_result.world
    problem = orch_result.problem
    tasks = orch_result.task or []

    # Structural metrics
    checker = WorldCheckTool()
    check_result = checker.check(world)
    src_result["worldcheck_passed"] = check_result.passed
    src_result["num_nodes"] = len(world.nodes)
    src_result["num_edges"] = len(world.edges)
    src_result["scenario_title"] = world.scenario_title or ""
    src_result["num_tasks"] = len(tasks)
    src_result["eval_types"] = list(set(t.type.value for t in tasks))

    print(f"  OK in {src_result['orchestrator_time_s']}s")
    print(f"  Title: {src_result['scenario_title'][:60]}")
    print(f"  Nodes: {len(world.nodes)}, Edges: {len(world.edges)}")
    print(f"  WorldCheck: {'PASS' if check_result.passed else 'FAIL'}")
    print(f"  Tasks: {len(tasks)} ({', '.join(src_result['eval_types'])})")

    # Save SRC data
    src_result["world"] = world.model_dump(mode="json")
    src_result["problem"] = problem.model_dump(mode="json")
    src_result["tasks_data"] = [t.model_dump(mode="json") for t in tasks]
    if hasattr(orch_result, "case_plan") and orch_result.case_plan:
        src_result["case_plan"] = orch_result.case_plan.model_dump(mode="json")

    # --- Phase 2: Agent on each task ---
    if not tasks:
        print("  No tasks generated, skipping agent")
        return src_result

    for i, task in enumerate(tasks, 1):
        print(f"\n  Task {i}/{len(tasks)}: {task.type.value}")
        print(f"    Q: {task.question[:80]}...")

        task_result = run_agent_on_task(agent, world, problem, task, seed)
        src_result["task_results"].append(task_result)

        # Print task result
        status = "OK" if task_result["submitted"] else "NO SUBMIT"
        score_str = (
            f"{task_result['score']:.4f}" if task_result["score"] is not None else "N/A"
        )
        fm = task_result["failure_mode"] or "-"
        errs = task_result["format_errors"]
        print(
            f"    -> {status} | score={score_str} | "
            f"budget={task_result['budget_used']} | "
            f"errors={errs} | mode={fm} | {task_result['time_s']}s"
        )

    return src_result


# ---------------------------------------------------------------------------
# Diagnostic report
# ---------------------------------------------------------------------------

def generate_report(results: list[dict]) -> str:
    """Generate the diagnostic report from all SRC results."""
    lines = []
    lines.append("")
    lines.append("=" * 70)
    lines.append("S.2 DIAGNOSTIC REPORT")
    lines.append("=" * 70)

    # --- Overall SRC stats ---
    total_srcs = len(results)
    completed = sum(1 for r in results if r["orchestrator_completed"])
    total_tasks = sum(len(r["task_results"]) for r in results)

    lines.append(f"\nSRCs: {completed}/{total_srcs} completed")
    lines.append(f"Tasks: {total_tasks} total")

    # --- Per-eval-type breakdown ---
    type_metrics = defaultdict(lambda: {
        "count": 0,
        "submitted": 0,
        "scores": [],
        "format_errors": 0,
        "failure_modes": defaultdict(int),
        "budget_used": [],
        "times": [],
    })

    for r in results:
        for tr in r["task_results"]:
            tt = tr["task_type"]
            m = type_metrics[tt]
            m["count"] += 1
            if tr["submitted"]:
                m["submitted"] += 1
            if tr["score"] is not None:
                m["scores"].append(tr["score"])
            m["format_errors"] += tr["format_errors"]
            m["budget_used"].append(tr["budget_used"])
            m["times"].append(tr["time_s"])
            if tr["failure_mode"]:
                m["failure_modes"][tr["failure_mode"]] += 1

    lines.append(f"\n{'='*70}")
    lines.append("PER EVAL TYPE")
    lines.append(f"{'='*70}")

    header = f"  {'Type':<25} {'N':>3} {'Sub%':>5} {'Score':>8} {'Errs':>5} {'Failures'}"
    lines.append(header)
    lines.append("  " + "-" * 65)

    for tt in sorted(type_metrics.keys()):
        m = type_metrics[tt]
        n = m["count"]
        sub_pct = f"{m['submitted']/n*100:.0f}%" if n > 0 else "-"
        if m["scores"]:
            mean_score = sum(m["scores"]) / len(m["scores"])
            score_str = f"{mean_score:.4f}"
        else:
            score_str = "N/A"
        errs = m["format_errors"]
        failures = ", ".join(
            f"{mode}:{cnt}" for mode, cnt in sorted(m["failure_modes"].items())
        ) or "-"
        lines.append(f"  {tt:<25} {n:>3} {sub_pct:>5} {score_str:>8} {errs:>5} {failures}")

    # --- Global failure mode summary ---
    all_failures = defaultdict(int)
    for r in results:
        for tr in r["task_results"]:
            if tr["failure_mode"]:
                all_failures[tr["failure_mode"]] += 1

    lines.append(f"\n{'='*70}")
    lines.append("FAILURE MODES")
    lines.append(f"{'='*70}")

    if all_failures:
        for mode, cnt in sorted(all_failures.items(), key=lambda x: -x[1]):
            pct = cnt / total_tasks * 100 if total_tasks > 0 else 0
            lines.append(f"  {mode}: {cnt}/{total_tasks} ({pct:.0f}%)")
    else:
        lines.append("  None detected")

    # --- Per-SRC summary table ---
    lines.append(f"\n{'='*70}")
    lines.append("PER SRC SUMMARY")
    lines.append(f"{'='*70}")

    lines.append(
        f"  {'ID':>3} {'Orch':>5} {'WC':>4} {'Tasks':>5} "
        f"{'Sub':>4} {'AvgSc':>7} {'Types':>30} {'Title'}"
    )
    lines.append("  " + "-" * 80)

    for r in results:
        cid = r["case_id"]
        orch = "OK" if r["orchestrator_completed"] else "FAIL"
        wc_val = r.get("worldcheck_passed")
        wc = "PASS" if wc_val else "FAIL" if wc_val is not None else "-"
        n_tasks = len(r["task_results"])
        n_sub = sum(1 for tr in r["task_results"] if tr["submitted"])
        scores = [tr["score"] for tr in r["task_results"] if tr["score"] is not None]
        avg_score = f"{sum(scores)/len(scores):.4f}" if scores else "N/A"
        types = ", ".join(sorted(set(tr["task_type"] for tr in r["task_results"])))[:30]
        title = r.get("scenario_title", "")[:25]
        lines.append(
            f"  {cid:>3} {orch:>5} {wc:>4} {n_tasks:>5} "
            f"{n_sub:>4} {avg_score:>7} {types:>30} {title}"
        )

    # --- Diagnostic signals ---
    lines.append(f"\n{'='*70}")
    lines.append("DIAGNOSTIC SIGNALS")
    lines.append(f"{'='*70}")

    # Types not seen
    all_types_seen = set()
    for r in results:
        for tr in r["task_results"]:
            all_types_seen.add(tr["task_type"])
    all_possible = {
        "infer_target", "next_best_observation", "hypothesis_selection",
        "causal_effect", "best_intervention", "adjustment_set",
        "compare_interventions", "should_condition", "infer_latent_cause",
    }
    missing = all_possible - all_types_seen
    if missing:
        lines.append(f"  Types NOT exercised: {sorted(missing)}")
    else:
        lines.append("  All 9 eval types exercised!")

    # Submission rate
    if total_tasks > 0:
        total_sub = sum(
            1 for r in results for tr in r["task_results"] if tr["submitted"]
        )
        lines.append(f"  Overall submission rate: {total_sub}/{total_tasks} "
                     f"({total_sub/total_tasks*100:.0f}%)")

    # Format error rate
    total_errs = sum(
        tr["format_errors"] for r in results for tr in r["task_results"]
    )
    if total_errs > 0:
        lines.append(f"  Total format errors: {total_errs} across {total_tasks} tasks")

    lines.append("=" * 70)

    text = "\n".join(lines)
    print(text)
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="S.2 Diagnostic pipeline: real SRCs, agent on all tasks"
    )
    parser.add_argument("--cases", type=int, default=3, help="Number of SRCs (max 5)")
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output directory (default: experiments/diag_TIMESTAMP)"
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

    # Output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("experiments") / f"diag_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"S.2 Diagnostic Pipeline: {n_cases} SRCs")
    print(f"Output: {output_dir}")
    print(f"Seed: {args.seed}")

    agent = AgentSolver(max_iterations=15)
    results = []

    for i in range(n_cases):
        goal = GOALS[i]
        seed = args.seed + i
        src_result = run_single_src(goal, i + 1, seed, agent)
        results.append(src_result)

    # --- Generate report ---
    report_text = generate_report(results)

    # --- Save results ---
    # Summary (without full trajectories and world data — keep it small)
    summary = []
    for r in results:
        s = {
            k: v for k, v in r.items()
            if k not in ("world", "problem", "tasks_data", "case_plan")
        }
        # Strip trajectories from task_results for summary
        s["task_results"] = [
            {k: v for k, v in tr.items() if k != "trajectory"}
            for tr in r.get("task_results", [])
        ]
        summary.append(s)

    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    report_path = output_dir / "report.txt"
    report_path.write_text(report_text, encoding="utf-8")

    # Save per-SRC detailed data (includes trajectories)
    cases_dir = output_dir / "cases"
    cases_dir.mkdir(exist_ok=True)

    for r in results:
        cid = r["case_id"]

        # SRC data (world + problem + tasks)
        src_data = {}
        if "world" in r:
            src_data["world"] = r["world"]
        if "problem" in r:
            src_data["problem"] = r["problem"]
        if "tasks_data" in r:
            src_data["tasks"] = r["tasks_data"]
        if "case_plan" in r:
            src_data["case_plan"] = r["case_plan"]

        if src_data:
            src_path = cases_dir / f"case_{cid:03d}_src.json"
            src_path.write_text(
                json.dumps(src_data, indent=2, default=str), encoding="utf-8"
            )

        # Task results with trajectories
        for tr in r.get("task_results", []):
            task_type = tr["task_type"]
            task_path = cases_dir / f"case_{cid:03d}_{task_type}.json"
            task_path.write_text(
                json.dumps(tr, indent=2, default=str), encoding="utf-8"
            )

    # Save config
    config = {
        "n_cases": n_cases,
        "seed": args.seed,
        "goals": GOALS[:n_cases],
        "timestamp": datetime.now().isoformat(),
        "script": "diagnostic_batch.py",
        "version": "S.2",
    }
    config_path = output_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    print(f"\nResults saved to: {output_dir}/")
    print("  summary.json  - per-SRC metrics (no trajectories)")
    print("  report.txt    - diagnostic report")
    print("  cases/        - per-task detail + trajectories")
    print("  config.json   - experiment config")


if __name__ == "__main__":
    main()
