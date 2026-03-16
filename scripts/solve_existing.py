"""Run the solver on an existing SRC (from src.json).

Usage:
    python scripts/solve_existing.py experiments/eval_smoking_v3/src.json
    python scripts/solve_existing.py experiments/eval_smoking_v3_abstract/src.json
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/solve_existing.py <src.json>")
        sys.exit(1)

    src_path = sys.argv[1]
    output_dir = os.path.dirname(src_path)

    with open(src_path, encoding="utf-8") as f:
        src = json.load(f)

    from openai import OpenAI

    from sreg.agent.agent import AgentSolver
    from sreg.models.research_problem import ResearchProblem
    from sreg.models.task import Task
    from sreg.models.world import World

    world = World(**src["world"])
    problem = ResearchProblem(**src["problem"])
    tasks = [Task(**t) for t in src["tasks"]]

    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    model = os.environ.get("AZURE_MODEL", "gpt-5.4")
    client = OpenAI(base_url=base_url, api_key=api_key)

    mode = src.get("metadata", {}).get("semantic_mode", "realistic")
    print(f"=== Solving: {os.path.basename(output_dir)} (mode: {mode}) ===")
    print(f"  Title: {world.scenario_title}")
    print(f"  Tasks: {len(tasks)}")
    print(f"  Model: {model}")
    print()

    agent = AgentSolver(model=model, max_iterations=25, client=client)
    case_result = agent.solve_case(world, problem, tasks, seed=42)

    # Extract scores from agent results (solver scores internally)
    results = []
    print("Results:")
    print(f"  {'Type':<25} {'Score':>8} {'Verdict':<12}")
    print(f"  {'-'*25} {'-'*8} {'-'*12}")

    for i, task in enumerate(tasks):
        tr = case_result.task_results.get(i + 1)
        tt = str(task.type.value if hasattr(task.type, "value") else task.type)

        if tr is None or tr.submitted_answer is None:
            results.append({"type": tt, "score": 0.0, "verdict": "NO_SUBMIT"})
            print(f"  {tt:<25} {'0.00':>8} {'NO_SUBMIT':<12}")
            continue

        if tr.score is None:
            results.append({"type": tt, "score": 0.0, "verdict": "NO_SCORE",
                            "answer": str(tr.submitted_answer)[:100]})
            print(f"  {tt:<25} {'0.00':>8} {'NO_SCORE':<12}")
            continue

        score_val = tr.score.functional_score
        if score_val < 0.1:
            verdict = "GOOD"
        elif score_val < 0.5:
            verdict = "OK"
        else:
            verdict = "POOR"

        results.append({
            "type": tt,
            "score": score_val,
            "verdict": verdict,
            "answer": str(tr.submitted_answer)[:100],
        })
        print(f"  {tt:<25} {score_val:>8.3f} {verdict:<12}")

    # Save results
    avg_score = sum(r["score"] for r in results) / max(len(results), 1)
    output = {
        "mode": mode,
        "model": model,
        "title": world.scenario_title,
        "avg_score": avg_score,
        "tasks": results,
        "budget_used": case_result.budget_used,
        "budget_total": case_result.budget_total,
    }

    result_path = os.path.join(output_dir, "solve_result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n  Average score: {avg_score:.3f}")
    print(f"  Saved: {result_path}")


if __name__ == "__main__":
    main()
