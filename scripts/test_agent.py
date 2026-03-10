#!/usr/bin/env python3
"""Test the LLM agent solver: run on a generated problem and compare with teacher.

Usage:
    python scripts/test_agent.py [--seed SEED] [--nodes NODES] [--budget BUDGET]
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
)
from sreg.env.episode import EpisodeRunner
from sreg.models.episode import Action, ActionType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

# -------------------------------------------------------------------
# Teacher solver
# -------------------------------------------------------------------


def run_teacher(world, problem, seed):
    """Run the teacher solver step by step."""
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    ep_tool = EpisodeGenTool()
    episode = ep_tool.generate(world, EpisodeGenConfig(budget=problem.budget, seed=seed))
    runner = EpisodeRunner(world, episode, true_state)

    obs_nodes = list(episode.available_nodes)
    evidence: dict[str, str] = {}

    lines = [_c(_C.DIM, "El teacher usa inferencia bayesiana exacta."), ""]

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
        ig = solver.information_gain(problem.target_node, dict(list(evidence.items())[:-1]), node)
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
    """Run a random baseline (uniform prior, no observations)."""
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
# LLM Agent with real-time output
# -------------------------------------------------------------------


def _agent_callback(event_type: str, data: dict) -> None:
    """Callback for real-time agent output."""
    if event_type == "thinking":
        content = data["content"]
        # Truncate long thinking
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
        _safe_print(
            f"  {_c(_C.GREEN, '>>>')} submit {_fmt_dist(dist)}"
        )
    elif event_type == "error":
        _safe_print(
            f"  {_c(_C.RED, '!!!')} Error en {data['tool']}: {data['error'][:80]}"
        )


def run_agent(world, problem, seed):
    """Run the LLM agent with step-by-step output."""
    _safe_print(_c(_C.BOLD + _C.BLUE, "\n+" + "-" * 78 + "+"))
    _safe_print(_c(_C.BOLD + _C.BLUE, "| AGENTE LLM"))
    _safe_print(_c(_C.BOLD + _C.BLUE, "+" + "-" * 78 + "+"))
    _safe_print("")

    agent = AgentSolver(max_iterations=15)
    result = agent.solve(world, problem, seed=seed, on_step=_agent_callback)

    _safe_print("")

    # Summary
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
    parser = argparse.ArgumentParser(description="Test LLM agent solver")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--nodes", type=int, default=6)
    parser.add_argument("--budget", type=int, default=4)
    parser.add_argument("--edge-strength", type=float, default=0.7)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--save-trajectory", type=str, default=None,
        help="Save agent trajectory + comparison JSON to this directory",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    else:
        # Silence noisy loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("sreg.agent.agent").setLevel(logging.WARNING)

    # Generate world and problem
    _safe_print(_c(_C.BOLD, "\n=== SREG Agent Test ===\n"))

    gen = WorldGenTool()
    world = gen.generate(
        WorldGenConfig(
            seed=args.seed,
            num_nodes=args.nodes,
            edge_strength=args.edge_strength,
        )
    )

    builder = ProblemBuilder()
    problem = builder.build(world, budget=args.budget)

    # Show the problem the agent will see
    show_research_problem(problem)
    _safe_print("")

    # Run teacher, random, and agent
    teacher_score, teacher_posterior, true_state = run_teacher(world, problem, args.seed)
    _safe_print("")
    random_score = run_random_baseline(world, problem, args.seed)
    agent_result = run_agent(world, problem, args.seed)

    # Final comparison
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

    # Save trajectory if requested
    if args.save_trajectory:
        from pathlib import Path

        from sreg.harness.agent_trajectory import extract_agent_trajectory
        from sreg.harness.comparison import compare_trajectories
        from sreg.harness.trajectory import generate_teacher_trajectory

        out_dir = Path(args.save_trajectory)
        out_dir.mkdir(parents=True, exist_ok=True)

        agent_traj = extract_agent_trajectory(
            agent_result, problem, world_id=world.id, seed=args.seed
        )
        teacher_traj = generate_teacher_trajectory(world, problem, seed=args.seed)
        comp = compare_trajectories(teacher_traj, agent_traj)

        prefix = f"seed{args.seed}_n{args.nodes}"
        traj_path = out_dir / f"{prefix}_agent_trajectory.json"
        comp_path = out_dir / f"{prefix}_comparison.json"

        traj_path.write_text(agent_traj.model_dump_json(indent=2), encoding="utf-8")
        comp_path.write_text(comp.model_dump_json(indent=2), encoding="utf-8")

        _safe_print(f"Trajectory saved: {traj_path}")
        _safe_print(f"Comparison saved: {comp_path}")


if __name__ == "__main__":
    main()
