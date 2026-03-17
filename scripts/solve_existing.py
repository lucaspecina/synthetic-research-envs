"""Run the solver on an existing SRC (from src.json).

Generates full_case.md + solve_result.json, same as generate_src.py --solve.

Usage:
    python scripts/solve_existing.py experiments/eval_smoking_v3/src.json
    python scripts/solve_existing.py experiments/eval_smoking_v3_abstract/src.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Solve an existing SRC")
    parser.add_argument("src_json", help="Path to src.json")
    parser.add_argument("-o", "--output", help="Output directory (default: same as src.json)")
    args = parser.parse_args()

    src_path = args.src_json
    output_dir = args.output or os.path.dirname(src_path)

    with open(src_path, encoding="utf-8") as f:
        src = json.load(f)

    from openai import OpenAI

    from sreg.agent.agent import AgentSolver
    from sreg.models.research_problem import ResearchProblem
    from sreg.models.task import Task, TaskType
    from sreg.models.world import World

    world = World(**src["world"])
    problem = ResearchProblem(**src["problem"])
    tasks = [Task(**t) for t in src["tasks"]]

    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    model = os.environ.get("AZURE_SOLVER_MODEL", os.environ.get("AZURE_MODEL", "gpt-5.4"))
    client = OpenAI(base_url=base_url, api_key=api_key)

    mode = src.get("metadata", {}).get("semantic_mode", "realistic")
    print(f"=== Solving: {os.path.basename(output_dir)} (mode: {mode}) ===")
    print(f"  Title: {world.scenario_title}")
    print(f"  Tasks: {len(tasks)}")
    print(f"  Model: {model}")
    print()

    agent = AgentSolver(model=model, max_iterations=40, client=client)
    case_result = agent.solve_case(world, problem, tasks, seed=42)

    # Build task_details
    task_details = []
    print("Results:")
    print(f"  {'Type':<25} {'Score':>8} {'Verdict':<12}")
    print(f"  {'-'*25} {'-'*8} {'-'*12}")

    for i, task in enumerate(tasks, 1):
        tr = case_result.task_results.get(i)
        tt = str(task.type.value if hasattr(task.type, "value") else task.type)

        if tr is None or tr.submitted_answer is None:
            task_details.append((i, task, tr, "NO SUBMIT", "-"))
            print(f"  {tt:<25} {'0.00':>8} {'NO_SUBMIT':<12}")
            continue

        if tr.score is None:
            task_details.append((i, task, tr, "NO SCORE", "-"))
            print(f"  {tt:<25} {'0.00':>8} {'NO_SCORE':<12}")
            continue

        score_val = tr.score.functional_score
        score_str = f"{score_val:.4f}"
        # Choice/non-distribution types: 1.0=correct, 0.0=wrong (higher=better)
        # Distribution types (KL): 0.0=perfect, higher=worse (lower=better)
        higher_is_better = task.type not in (
            TaskType.INFER_TARGET, TaskType.CAUSAL_EFFECT,
            TaskType.INFER_LATENT_CAUSE,
        )
        if higher_is_better:
            verdict = "GOOD" if score_val > 0.9 else "OK" if score_val > 0.5 else "POOR"
        else:
            verdict = "GOOD" if score_val < 0.1 else "OK" if score_val < 0.5 else "POOR"

        task_details.append((i, task, tr, verdict, score_str))
        print(f"  {tt:<25} {score_val:>8.3f} {verdict:<12}")

    # --- Build full_case.md ---
    from generate_src import build_dag_section

    full_lines = []
    full_lines.append(f"# Full Case Report: {world.scenario_title or world.id}")
    full_lines.append("")
    full_lines.append(f"Mode: {mode}")
    full_lines.append(f"Tools: python_exec + think + submit")
    full_lines.append(f"Tasks: {len(tasks)}")
    full_lines.append("")

    # Part 0: Ground truth
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 0: Ground truth (hidden from solver)")
    full_lines.append("")
    full_lines.extend(build_dag_section(world, tasks))

    # Part 1: What the solver received
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 1: What the solver received")
    full_lines.append("")

    # Dataset summary (system prompt details in briefing.md)
    full_lines.append("## Datasets (see briefing.md for full problem statement)")
    full_lines.append("")
    for idx, asset in enumerate(problem.data_assets):
        if asset.format == "tabular" and asset.data:
            headers = [k for k in asset.data[0].keys() if k != "sample_id"]
            df_name = "df" if idx == 0 else f"df_{idx}"
            full_lines.append(
                f"- **{df_name}**: {len(asset.data)} rows, "
                f"{len(headers)} vars ({', '.join(headers[:5])}...)"
            )
    full_lines.append("")
    full_lines.append(f"Questions: {len(tasks)}")
    for i, t in enumerate(tasks, 1):
        q_short = t.question[:80] + "..." if len(t.question) > 80 else t.question
        full_lines.append(f"  {i}. ({t.type}) {q_short}")
    full_lines.append("")

    # Part 2: What the solver did
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 2: What the solver did")
    full_lines.append("")

    for msg in case_result.messages:
        role = msg.get("role", "?")

        if role == "system":
            full_lines.append("> *(system prompt -- shown above)*")
            full_lines.append("")
        elif role == "user":
            content = msg.get("content", "")
            full_lines.append(f"> **[USER]** {content}")
            full_lines.append("")
        elif role == "assistant":
            content = msg.get("content")
            tool_calls = msg.get("tool_calls", [])
            if content:
                full_lines.append("**[SOLVER THINKS]**")
                full_lines.append("")
                full_lines.append(content)
                full_lines.append("")
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "?")
                fn_args_raw = fn.get("arguments", "{}")
                try:
                    fn_args = json.loads(fn_args_raw)
                except (json.JSONDecodeError, TypeError):
                    fn_args = {"raw": fn_args_raw}
                if fn_name == "think":
                    reasoning = fn_args.get("reasoning", "")
                    full_lines.append("**[SOLVER REASONS]**")
                    full_lines.append("")
                    full_lines.append(f"> {reasoning}")
                elif fn_name == "python_exec" and "code" in fn_args:
                    full_lines.append("**[SOLVER RUNS CODE]**")
                    full_lines.append("```python")
                    full_lines.append(fn_args["code"])
                    full_lines.append("```")
                elif fn_name == "submit":
                    full_lines.append("**[SOLVER SUBMITS]**")
                    full_lines.append("```json")
                    full_lines.append(json.dumps(fn_args, indent=2, ensure_ascii=False))
                    full_lines.append("```")
                elif fn_name == "research_action":
                    action_id = fn_args.get("action_id", "?")
                    full_lines.append(f"**[SOLVER MEASURES]** `{action_id}`")
                else:
                    full_lines.append(f"**[SOLVER CALLS]** `{fn_name}`")
                    full_lines.append("```json")
                    full_lines.append(json.dumps(fn_args, indent=2, ensure_ascii=False))
                    full_lines.append("```")
                full_lines.append("")
        elif role == "tool":
            content_raw = msg.get("content", "{}")
            try:
                content = json.loads(content_raw)
            except (json.JSONDecodeError, TypeError):
                content = {"raw": content_raw}
            if isinstance(content, dict) and content.get("status") == "noted":
                pass
            elif isinstance(content, dict) and "output" in content and len(content) == 1:
                output = content["output"]
                if len(output) > 1200:
                    output = output[:1200] + "\n... (truncated)"
                full_lines.append("**[CODE OUTPUT]**")
                full_lines.append("```")
                full_lines.append(output)
                full_lines.append("```")
            elif isinstance(content, dict) and "findings" in content:
                findings = content["findings"]
                full_lines.append(f"**[FINDING]** {findings}")
            elif isinstance(content, dict) and content.get("status") == "submitted":
                q = content.get("question", "?")
                msg_text = content.get("message", "")
                full_lines.append(f"**[RECORDED Q{q}]** {msg_text}")
            elif isinstance(content, dict) and "error" in content:
                full_lines.append(f"**[ERROR]** {content['error']}")
            else:
                content_str = json.dumps(content, indent=2, ensure_ascii=False)
                if len(content_str) > 500:
                    content_str = content_str[:500] + "\n... (truncated)"
                full_lines.append("```json")
                full_lines.append(content_str)
                full_lines.append("```")
            full_lines.append("")

    # Part 3: Evaluation
    full_lines.append("---")
    full_lines.append("")
    full_lines.append("# Part 3: Evaluation")
    full_lines.append("")
    full_lines.append("| # | Type | Score | Verdict | Agent Answer | Correct Answer |")
    full_lines.append("| --- | --- | --- | --- | --- | --- |")
    for i, task, tr, verdict, score_str in task_details:
        ans = tr.submitted_answer if tr else None
        ans_str = str(ans)[:40] if ans else "-"
        correct_str = str(task.correct_answer)[:40]
        full_lines.append(
            f"| {i} | {task.type} | {score_str} | {verdict} | {ans_str} | {correct_str} |"
        )
    full_lines.append("")
    for i, task, tr, verdict, score_str in task_details:
        full_lines.append(f"### Question {i}: {task.type} -- {verdict}")
        full_lines.append("")
        q = task.question
        if len(q) > 300:
            q = q[:300] + "..."
        full_lines.append(f"**Question:** {q}")
        full_lines.append("")
        full_lines.append("**Correct answer:**")
        correct = task.correct_answer
        if isinstance(correct, dict):
            for k, v in sorted(correct.items()):
                full_lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        else:
            full_lines.append(f"- {correct}")
        full_lines.append("")
        full_lines.append("**Solver answer:**")
        ans = tr.submitted_answer if tr else None
        if isinstance(ans, dict):
            for k, v in sorted(ans.items()):
                full_lines.append(f"- {k}: {v:.4f}" if isinstance(v, float) else f"- {k}: {v}")
        elif ans is not None:
            full_lines.append(f"- {ans}")
        else:
            full_lines.append("- *(no answer)*")
        full_lines.append("")

    full_path = os.path.join(output_dir, "full_case.md")
    with open(full_path, "w", encoding="utf-8") as f:
        f.write("\n".join(full_lines))
    print(f"\n  Saved: {full_path}")

    # Save solve_result.json
    results_list = []
    for i, task, tr, verdict, score_str in task_details:
        tt = str(task.type.value if hasattr(task.type, "value") else task.type)
        entry = {"type": tt}
        if tr and tr.submitted_answer is not None and tr.score is not None:
            entry["score"] = tr.score.functional_score
            entry["verdict"] = verdict
            entry["answer"] = str(tr.submitted_answer)[:100]
        else:
            entry["score"] = 0.0
            entry["verdict"] = verdict
        results_list.append(entry)

    avg_score = sum(r["score"] for r in results_list) / max(len(results_list), 1)
    solve_output = {
        "mode": mode,
        "model": model,
        "title": world.scenario_title,
        "avg_score": avg_score,
        "tasks": results_list,
    }
    result_path = os.path.join(output_dir, "solve_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(solve_output, f, indent=2, ensure_ascii=False)

    print(f"  Saved: {result_path}")
    print(f"\n  Average score: {avg_score:.3f}")


if __name__ == "__main__":
    main()
