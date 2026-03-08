#!/usr/bin/env python3
"""End-to-end test: orchestrator generates a semantic world, agent solves it.

Pipeline:
    Orchestrator (LLM) -> semantic world + ResearchProblem
        -> AgentSolver solves it
        -> Compare with teacher + random baseline

Usage:
    python scripts/test_e2e.py [--goal GOAL] [--budget BUDGET] [--seed SEED]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.agent.agent import AgentSolver
from sreg.display import (
    _C,
    _box,
    _c,
    _safe_print,
    show_agent_comparison,
    show_research_problem,
    show_world,
)
from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionType
from sreg.orchestrator.orchestrator import Orchestrator
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.verifier import VerifierTool

# -------------------------------------------------------------------
# Orchestrator with step-by-step output
# -------------------------------------------------------------------


def _safe(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


def run_orchestrator(goal: str, model: str | None = None) -> tuple:
    """Run the orchestrator with verbose step-by-step output.

    Returns (world, problem) or (None, None) on failure.
    """
    _safe_print(_c(_C.BOLD + _C.BLUE, "\n+" + "-" * 78 + "+"))
    _safe_print(_c(_C.BOLD + _C.BLUE, "| FASE 1: ORCHESTRATOR — Generando mundo semantico"))
    _safe_print(_c(_C.BOLD + _C.BLUE, "+" + "-" * 78 + "+"))
    _safe_print("")

    _safe_print(f"  {_c(_C.DIM, 'Goal:')} {goal}")
    _safe_print(f"  {_c(_C.DIM, 'Model:')} {model or os.environ.get('AZURE_MODEL', 'gpt-4o')}")
    _safe_print("")

    o = Orchestrator(model=model) if model else Orchestrator()

    # Intercept tool calls for display
    original_dispatch = o._dispatch_tool
    step_count = [0]

    def patched_dispatch(name, fn_args, result):
        step_count[0] += 1
        tool_result = original_dispatch(name, fn_args, result)

        if "error" in tool_result:
            _safe_print(
                f"  {_c(_C.RED, f'[{step_count[0]}]')} {name} "
                f"-> {_c(_C.RED, 'ERROR:')} {_safe(str(tool_result['error'])[:120])}"
            )
        else:
            _show_orch_tool(step_count[0], name, tool_result)

        return tool_result

    o._dispatch_tool = patched_dispatch

    result = o.run(goal)

    _safe_print("")
    if result.world and result.problem:
        _safe_print(
            f"  {_c(_C.GREEN, 'OK')} Orchestrator completo en {step_count[0]} tool calls."
        )
    else:
        _safe_print(
            f"  {_c(_C.RED, 'FAIL')} Orchestrator no completo el pipeline."
        )
        if not result.world:
            _safe_print(f"  {_c(_C.RED, '  - No se genero mundo')}")
        if not result.problem:
            _safe_print(f"  {_c(_C.RED, '  - No se genero problema')}")

    return result.world, result.problem


def _show_orch_tool(n: int, name: str, result: dict) -> None:
    """Show concise orchestrator tool result."""
    label = _c(_C.CYAN, f"[{n}]")

    if name == "world_gen":
        nodes = result.get("nodes", [])
        node_list = ", ".join(n_["name"] for n_ in nodes)
        _safe_print(
            f"  {label} {_c(_C.BOLD, 'world_gen')} -> "
            f"{result['num_nodes']} nodos, {result['num_edges']} edges, "
            f"dificultad: {result['difficulty']}"
        )
        _safe_print(f"         Nodos: {node_list}")

    elif name == "world_check":
        status = _c(_C.GREEN, "PASS") if result["passed"] else _c(_C.RED, "FAIL")
        _safe_print(f"  {label} {_c(_C.BOLD, 'world_check')} -> {status}")
        if not result["passed"]:
            for f in result.get("failures", []):
                _safe_print(f"         - {f}")

    elif name == "apply_semantics":
        title = _safe(result.get("scenario_title", "") or "")
        nodes = [n_["name"] for n_ in result.get("nodes", [])]
        _safe_print(
            f"  {label} {_c(_C.BOLD, 'apply_semantics')} -> "
            f"{_c(_C.MAGENTA, title)}"
        )
        _safe_print(f"         Nodos: {', '.join(nodes)}")

    elif name == "build_problem":
        title = _safe(result.get("title", "") or "")
        _safe_print(
            f"  {label} {_c(_C.BOLD, 'build_problem')} -> "
            f"{_c(_C.MAGENTA, title)}"
        )
        _safe_print(
            f"         Target: {result.get('target_node')} "
            f"({', '.join(result.get('target_states', []))}), "
            f"budget: {result.get('budget')}"
        )

    elif name == "episode_gen":
        _safe_print(
            f"  {label} {_c(_C.BOLD, 'episode_gen')} -> "
            f"budget={result.get('budget')}, "
            f"nodes={', '.join(result.get('available_nodes', []))}"
        )

    elif name == "task_gen":
        _safe_print(
            f"  {label} {_c(_C.BOLD, 'task_gen')} -> "
            f"type={result.get('type')}, target={result.get('target_node')}"
        )

    else:
        _safe_print(f"  {label} {_c(_C.BOLD, name)} -> OK")


# -------------------------------------------------------------------
# Teacher solver
# -------------------------------------------------------------------


def run_teacher(world, problem, seed):
    """Run the teacher (exact Bayesian inference) and return score + posterior."""
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    ep_tool = EpisodeGenTool()
    episode = ep_tool.generate(world, EpisodeGenConfig(budget=problem.budget, seed=seed))
    runner = EpisodeRunner(world, episode, true_state)

    obs_nodes = list(episode.available_nodes)
    evidence: dict[str, str] = {}

    lines = [_c(_C.DIM, "Inferencia bayesiana exacta."), ""]

    for step in range(min(episode.budget, len(obs_nodes))):
        available = [n for n in obs_nodes if n not in evidence]
        if not available:
            break
        output = solver.optimal_action(problem.target_node, evidence, available)
        if output.recommended_action is None:
            break
        result = runner.step(output.recommended_action)
        node = result.observation.node
        state = result.observation.state
        evidence[node] = state
        ig = solver.information_gain(
            problem.target_node, dict(list(evidence.items())[:-1]), node
        )
        lines.append(
            f"  {_c(_C.CYAN, f'Paso {step + 1}:')} observe "
            f"{_c(_C.BOLD, node)} = {_c(_C.YELLOW, state)}  "
            f"(IG: {ig:.4f} bits)"
        )

    final_posterior = runner.true_posterior(problem.target_node)
    runner.step(Action(type=ActionType.SUBMIT, answer=final_posterior, confidence=1.0))

    verifier = VerifierTool()
    score = verifier.score(
        agent_posterior=final_posterior,
        true_posterior=final_posterior,
        budget_used=len(evidence),
        budget_total=problem.budget,
    )

    lines.append("")
    lines.append(f"  {_c(_C.GREEN, 'Submit:')} {_fmt_dist(final_posterior)}")
    lines.append(f"  KL divergence: {_c(_C.BOLD, f'{score.functional_score:.6f}')}")
    lines.append(f"  Budget: {len(evidence)}/{problem.budget}")

    _safe_print(_box("TEACHER (optimo)", lines, _C.GREEN, width=80))

    return score, final_posterior, true_state


# -------------------------------------------------------------------
# Random baseline
# -------------------------------------------------------------------


def run_random_baseline(world, problem, seed):
    """Uniform distribution, no observations."""
    solver = ExactBayesSolver(world)
    true_posterior = solver.posterior(problem.target_node, {})
    uniform = {s: 1.0 / len(problem.target_states) for s in problem.target_states}

    verifier = VerifierTool()
    score = verifier.score(
        agent_posterior=uniform,
        true_posterior=true_posterior,
        budget_used=0,
        budget_total=problem.budget,
    )

    lines = [
        _c(_C.DIM, "Sin observaciones, distribucion uniforme."),
        "",
        f"  {_c(_C.GREEN, 'Submit:')} {_fmt_dist(uniform)}",
        f"  KL divergence: {_c(_C.BOLD, f'{score.functional_score:.6f}')}",
    ]

    _safe_print(_box("RANDOM BASELINE", lines, _C.RED, width=80))
    return score


# -------------------------------------------------------------------
# LLM Agent
# -------------------------------------------------------------------


def _agent_callback(event_type: str, data: dict) -> None:
    """Real-time agent output callback."""
    if event_type == "thinking":
        content = data["content"]
        if len(content) > 200:
            content = content[:200] + "..."
        iteration = data["iteration"]
        label = _c(_C.DIM, f"[iter {iteration}]")
        _safe_print(f"  {label} {_c(_C.WHITE, content)}")
    elif event_type == "observe":
        _safe_print(
            f"  {_c(_C.CYAN, '>>>')} observe "
            f"{_c(_C.BOLD, data['variable'])} = "
            f"{_c(_C.YELLOW, data['observed_state'])}  "
            f"(budget restante: {data['remaining_budget']})"
        )
    elif event_type == "submit":
        dist = data.get("distribution", {})
        _safe_print(f"  {_c(_C.GREEN, '>>>')} submit {_fmt_dist(dist)}")
    elif event_type == "error":
        _safe_print(
            f"  {_c(_C.RED, '!!!')} Error en {data['tool']}: {data['error'][:80]}"
        )


def run_agent(world, problem, seed):
    """Run the LLM agent with real-time output."""
    _safe_print(_c(_C.BOLD + _C.BLUE, "\n+" + "-" * 78 + "+"))
    _safe_print(_c(_C.BOLD + _C.BLUE, "| FASE 2: AGENTE LLM — Resolviendo el problema"))
    _safe_print(_c(_C.BOLD + _C.BLUE, "+" + "-" * 78 + "+"))
    _safe_print("")

    agent = AgentSolver(max_iterations=15)
    result = agent.solve(world, problem, seed=seed, on_step=_agent_callback)

    _safe_print("")

    lines = []
    if result.submitted_answer:
        lines.append(f"  {_c(_C.GREEN, 'Submit:')} {_fmt_dist(result.submitted_answer)}")
        if result.reasoning:
            reason = result.reasoning[:120]
            lines.append(f"  {_c(_C.DIM, 'Razonamiento:')} {reason}")
        if result.confidence is not None:
            lines.append(f"  Confianza: {result.confidence:.2f}")
        lines.append(
            f"  KL divergence: {_c(_C.BOLD, f'{result.score.functional_score:.6f}')}"
        )
        lines.append(f"  Budget: {result.budget_used}/{result.budget_total}")
        lines.append(f"  Observaciones: {len(result.observations)}")
    else:
        lines.append(f"  {_c(_C.RED + _C.BOLD, 'El agente no envio respuesta!')}")

    _safe_print(_box("RESULTADO AGENTE", lines, _C.BLUE, width=80))
    return result


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _fmt_dist(dist: dict[str, float]) -> str:
    parts = [f"{k}: {v:.3f}" for k, v in sorted(dist.items())]
    return "{" + ", ".join(parts) + "}"


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="End-to-end: orchestrator -> agent")
    parser.add_argument(
        "--goal",
        type=str,
        default=(
            "Generate a research problem about marine ecology in a fictional "
            "archipelago, medium difficulty, 6 nodes, budget 4"
        ),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--budget", type=int, default=None, help="Override problem budget")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    else:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("sreg.agent.agent").setLevel(logging.WARNING)
        logging.getLogger("sreg.orchestrator.orchestrator").setLevel(logging.WARNING)

    _safe_print(_c(_C.BOLD, "\n=== SREG End-to-End: Orchestrator -> Agent ===\n"))

    # --- Phase 1: Orchestrator generates semantic world + problem ---
    world, problem = run_orchestrator(args.goal, model=args.model)

    if world is None or problem is None:
        _safe_print(_c(_C.RED + _C.BOLD, "\nOrchestrator fallo. Abortando.\n"))
        sys.exit(1)

    # Override budget if requested
    if args.budget is not None:
        problem = problem.model_copy(update={"budget": args.budget})

    # Show what the agent will see
    _safe_print("")
    show_world(world)
    _safe_print("")
    show_research_problem(problem)
    _safe_print("")

    # --- Phase 2: Teacher, random baseline, and agent ---
    teacher_score, teacher_posterior, true_state = run_teacher(world, problem, args.seed)
    _safe_print("")
    random_score = run_random_baseline(world, problem, args.seed)
    agent_result = run_agent(world, problem, args.seed)

    # --- Final comparison ---
    _safe_print("")
    show_agent_comparison(
        true_state_value=true_state[problem.target_node],
        teacher_kl=teacher_score.functional_score,
        random_kl=random_score.functional_score,
        agent_kl=agent_result.score.functional_score if agent_result.score else None,
        agent_budget_used=agent_result.budget_used,
        agent_budget_total=agent_result.budget_total,
    )
    _safe_print("")


if __name__ == "__main__":
    main()
