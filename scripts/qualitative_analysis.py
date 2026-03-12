#!/usr/bin/env python3
"""Qualitative analysis: generate SRCs and inspect agent reasoning step by step.

Produces a detailed text report showing:
1. The SRC (world, problem, tasks, evidence)
2. The agent's full reasoning trajectory (what it observes, why, what it submits)
3. The teacher's optimal trajectory for comparison
4. Scoring and verdict

Usage:
    python scripts/qualitative_analysis.py
    python scripts/qualitative_analysis.py --model gpt-5.4 --cases 2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.agent.agent import AgentResult, AgentSolver
from sreg.harness.diagnostic import (
    classify_failure_mode,
    compute_baseline_score,
    beats_baseline,
)
from sreg.models.task import Task, TaskType
from sreg.models.world import World
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_check import WorldCheckTool

# ---------------------------------------------------------------------------
# Goals — pick cases that exercise the problematic types
# ---------------------------------------------------------------------------

GOALS = [
    # Case 1: hypothesis_selection + adjustment_set (both failing)
    (
        "Generate a research problem about water contamination in a fictional "
        "mining region. Use dag_construct with 8 nodes. Design a research case "
        "with hypothesis_selection, adjustment_set, infer_target, and causal_effect."
    ),
    # Case 2: compare_interventions + best_intervention + should_condition
    (
        "Generate a research problem about crop disease spreading in a fictional "
        "valley. Use dag_construct with 8 nodes. Design a research case with "
        "compare_interventions, best_intervention, should_condition, and infer_target."
    ),
    # Case 3: infer_latent_cause + NBO + causal_effect
    (
        "Generate a research problem about declining fish populations in a fictional "
        "lake. Use dag_construct with 8 nodes. Design a research case with "
        "infer_latent_cause, next_best_observation, causal_effect, and hypothesis_selection."
    ),
]


def format_world_summary(world: World) -> str:
    """Readable summary of the world structure."""
    lines = []
    lines.append(f"  Nodes ({len(world.nodes)}):")
    for node in world.nodes:
        states_str = ", ".join(node.states)
        lines.append(f"    {node.name} ({node.type.value}): [{states_str}]")

    lines.append(f"\n  Edges ({len(world.edges)}):")
    for edge in world.edges:
        lines.append(f"    {edge.from_node} -> {edge.to_node}")

    return "\n".join(lines)


def format_problem_summary(problem) -> str:
    """Readable summary of the research problem."""
    lines = []
    lines.append(f"  Title: {problem.title}")
    lines.append(f"  Domain: {problem.domain}")
    lines.append(f"  Description: {problem.description[:300]}...")
    lines.append(f"  Research question: {problem.research_question}")
    lines.append(f"  Target: {problem.target_node} ({', '.join(problem.target_states)})")
    lines.append(f"  Budget: {problem.budget}")
    lines.append(f"  Actions: {len(problem.available_actions)}")
    for act in problem.available_actions:
        nodes_str = ", ".join(act.nodes) if act.nodes else act.node or "?"
        lines.append(f"    - {act.action_type.value}: {nodes_str}")

    if problem.data_assets:
        lines.append(f"  Data assets: {len(problem.data_assets)}")
        for da in problem.data_assets[:3]:
            desc = da.description[:100] if da.description else "no description"
            lines.append(f"    - {desc}...")

    if problem.theoretical_context:
        lines.append(f"  Theoretical context: {problem.theoretical_context[:200]}...")

    return "\n".join(lines)


def format_task_summary(task: Task) -> str:
    """Readable summary of a task."""
    lines = []
    lines.append(f"  Type: {task.type.value}")
    lines.append(f"  Question: {task.question}")
    if task.correct_answer:
        ans_str = json.dumps(task.correct_answer, indent=2)
        if len(ans_str) > 300:
            ans_str = ans_str[:300] + "..."
        lines.append(f"  Correct answer: {ans_str}")
    if task.hypotheses:
        lines.append("  Hypotheses:")
        for label, hyp in task.hypotheses.items():
            lines.append(f"    {label}: {hyp}")
    return "\n".join(lines)


def format_agent_trajectory(result: AgentResult, messages: list[dict]) -> str:
    """Extract and format the agent's reasoning from its message history."""
    lines = []
    step = 0

    for msg in messages:
        role = msg.get("role", "")

        if role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            content = msg.get("content", "")

            if content:
                lines.append(f"\n  [AGENT THINKS]: {content[:500]}")

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "?")
                args_raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                except json.JSONDecodeError:
                    args = args_raw

                if name == "observe":
                    step += 1
                    var = args.get("variable", "?")
                    lines.append(f"\n  [STEP {step}] OBSERVE: {var}")
                elif name == "submit":
                    step += 1
                    lines.append(f"\n  [STEP {step}] SUBMIT:")
                    reasoning = args.get("reasoning", "")
                    if reasoning:
                        lines.append(f"    Reasoning: {reasoning}")
                    submit_data = {k: v for k, v in args.items() if k != "reasoning"}
                    lines.append(f"    Data: {json.dumps(submit_data, indent=4)}")
                else:
                    step += 1
                    lines.append(f"\n  [STEP {step}] {name}: {json.dumps(args)}")

        elif role == "tool":
            content = msg.get("content", "")
            try:
                parsed = json.loads(content)
                lines.append(f"    -> Result: {json.dumps(parsed)}")
            except (json.JSONDecodeError, TypeError):
                if content:
                    lines.append(f"    -> Result: {content[:200]}")

    return "\n".join(lines)


def run_teacher_trajectory(world, problem, task, seed) -> str:
    """Show teacher's optimal strategy (without full episode replay)."""
    from sreg.harness.trajectory import generate_teacher_trajectory

    lines = []
    target = problem.target_node

    try:
        traj = generate_teacher_trajectory(world, problem, seed=seed)

        lines.append(f"  Target: {target}")
        lines.append(f"  Steps: {len(traj.steps)}")

        for i, step in enumerate(traj.steps, 1):
            lines.append(
                f"\n  [STEP {i}] OBSERVE: {step.action_node} = {step.observed_state} "
                f"(IG={step.info_gain:.4f})"
            )
            if step.posterior:
                dist = {s: round(v, 4) for s, v in step.posterior.items()}
                lines.append(f"    Posterior[{target}]: {dist}")

        if traj.final_posterior:
            dist = {s: round(v, 4) for s, v in traj.final_posterior.items()}
            lines.append(f"\n  Final teacher posterior[{target}]: {dist}")

    except Exception as e:
        lines.append(f"  Teacher trajectory failed: {e}")

    return "\n".join(lines)


def get_score_value(result: AgentResult) -> float | None:
    """Extract the numeric score from AgentResult."""
    if result.score is None:
        return None
    return result.score.functional_score


def get_verdict(task_type: TaskType, score_val: float | None) -> str:
    """Derive verdict from score value."""
    if score_val is None:
        return "N/A"
    # Distribution types: KL (lower = better)
    if task_type in {TaskType.INFER_TARGET, TaskType.CAUSAL_EFFECT, TaskType.INFER_LATENT_CAUSE}:
        if score_val < 0.1:
            return "EXCELLENT"
        elif score_val < 0.5:
            return "GOOD"
        elif score_val < 1.0:
            return "FAIR"
        elif score_val < 2.0:
            return "POOR"
        else:
            return "HIGH_KL"
    # Binary/choice types: 0 or 1
    if score_val >= 0.99:
        return "CORRECT"
    elif score_val > 0.5:
        return "PARTIAL"
    elif score_val > 0:
        return "PARTIAL"
    else:
        return "WRONG"


def main():
    parser = argparse.ArgumentParser(description="Qualitative analysis of agent reasoning")
    parser.add_argument("--model", type=str, default=None, help="Model to use")
    parser.add_argument("--cases", type=int, default=3, help="Number of cases (max 3)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    model = args.model or os.environ.get("AZURE_MODEL", "gpt-5.2-chat")

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sreg.orchestrator.orchestrator").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.WARNING)

    n_cases = min(args.cases, len(GOALS))
    goals = GOALS[:n_cases]

    if args.output:
        output_dir = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("experiments") / f"qualitative_{ts}"
    output_dir.mkdir(parents=True, exist_ok=True)

    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("QUALITATIVE ANALYSIS -- Agent Reasoning Step by Step")
    report_lines.append(f"Model: {model}")
    report_lines.append(f"Date: {datetime.now().isoformat()}")
    report_lines.append(f"Cases: {n_cases}")
    report_lines.append("=" * 80)

    for case_i, goal in enumerate(goals, 1):
        print(f"\n{'='*60}")
        print(f"CASE {case_i}/{n_cases}")
        print(f"{'='*60}")

        # 1. Generate SRC via orchestrator
        print(f"  Generating SRC with {model}...")
        orch = Orchestrator(model=model)
        orch_result = orch.run(goal)

        if not orch_result.world or not orch_result.problem:
            print(f"  FAILED: orchestrator did not complete")
            report_lines.append(f"\n\nCASE {case_i}: ORCHESTRATOR FAILED")
            continue

        world = orch_result.world
        problem = orch_result.problem
        tasks: list[Task] = orch_result.task or []

        # WorldCheck
        wc = WorldCheckTool()
        wc_result = wc.check(world)

        report_lines.append(f"\n\n{'='*80}")
        report_lines.append(f"CASE {case_i}: {problem.title}")
        report_lines.append(f"{'='*80}")
        report_lines.append(f"\nGoal: {goal}")
        report_lines.append(f"\nWorldCheck: {'PASS' if wc_result.passed else 'FAIL'}")

        report_lines.append(f"\n--- WORLD ---")
        report_lines.append(format_world_summary(world))

        report_lines.append(f"\n--- PROBLEM ---")
        report_lines.append(format_problem_summary(problem))

        print(f"  World: {len(world.nodes)} nodes, {len(world.edges)} edges")
        print(f"  Title: {problem.title}")
        print(f"  Tasks: {len(tasks)}")

        # 2. Run agent on each task
        agent = AgentSolver(model=model, max_iterations=15)

        for task_i, task in enumerate(tasks, 1):
            task_type = task.type

            report_lines.append(f"\n\n{'~'*60}")
            report_lines.append(f"TASK {task_i}: {task_type.value}")
            report_lines.append(f"{'~'*60}")
            report_lines.append(format_task_summary(task))

            print(f"\n  Task {task_i}: {task_type.value}")
            print(f"    Q: {task.question[:100]}...")

            # Run agent
            result = agent.solve(world, problem, seed=args.seed + case_i, task=task)

            # Extract trajectory from messages
            report_lines.append(f"\n--- AGENT TRAJECTORY ---")
            trajectory_text = format_agent_trajectory(result, result.messages)
            report_lines.append(trajectory_text)

            # Score
            score_val = get_score_value(result)
            verdict = get_verdict(task_type, score_val)

            report_lines.append(f"\n--- RESULT ---")
            report_lines.append(f"  Submitted: {result.submitted_answer}")
            report_lines.append(f"  Confidence: {result.confidence}")
            report_lines.append(f"  Budget used: {result.budget_used}/{result.budget_total}")
            report_lines.append(
                f"  Score: {score_val:.4f}" if score_val is not None else "  Score: N/A"
            )
            report_lines.append(f"  Verdict: {verdict}")

            # Baseline comparison
            baseline = compute_baseline_score(task_type, task.correct_answer)
            if baseline is not None and score_val is not None:
                beats = beats_baseline(task_type, score_val, baseline)
                report_lines.append(f"  Baseline (random): {baseline:.4f}")
                report_lines.append(f"  Beats baseline: {'YES' if beats else 'NO'}")

            # Failure mode
            fm = classify_failure_mode(
                task_type,
                result.submitted_answer is not None,
                score_val,
                result.budget_used,
                0,
                None,
            )
            if fm:
                report_lines.append(f"  Failure mode: {fm}")

            # Teacher trajectory (for infer_target tasks)
            if task_type == TaskType.INFER_TARGET:
                report_lines.append(f"\n--- TEACHER TRAJECTORY (optimal) ---")
                teacher_text = run_teacher_trajectory(
                    world, problem, task, args.seed + case_i
                )
                report_lines.append(teacher_text)

            score_str = f"{score_val:.4f}" if score_val is not None else "N/A"
            print(f"    Score: {score_str} ({verdict})")
            print(f"    Budget: {result.budget_used}/{result.budget_total}")
            if fm:
                print(f"    Failure: {fm}")

    # Save report
    report_text = "\n".join(report_lines)
    report_path = output_dir / "qualitative_report.txt"
    report_path.write_text(report_text, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"Report saved to: {report_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
