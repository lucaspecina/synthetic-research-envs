#!/usr/bin/env python3
"""Batch evaluation: generate problems, run agent + teacher, report metrics.

Usage:
    python scripts/batch_eval.py [--problems N] [--nodes NODES] [--budget BUDGET]
    python scripts/batch_eval.py --export-trajectories output.jsonl
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv()

from sreg.display import _C, _box, _c, _safe_print
from sreg.harness.eval import BatchEvaluator, ProblemResult
from sreg.harness.trajectory import export_trajectories, generate_teacher_trajectory
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def _on_problem(index: int, total: int, pr: ProblemResult) -> None:
    """Progress callback for each problem."""
    status = _c(_C.GREEN, "OK") if pr.agent_beats_random else _c(_C.RED, "FAIL")
    if not pr.agent_submitted:
        status = _c(_C.RED, "NO SUBMIT")

    agent_kl = f"{pr.agent_kl:.4f}" if pr.agent_kl is not None else "N/A"
    _safe_print(
        f"  [{index + 1}/{total}] seed={pr.seed:>3}  "
        f"teacher={pr.teacher_kl:.4f}  agent={agent_kl:>8}  "
        f"random={pr.random_kl:.4f}  "
        f"true={pr.true_state:<8} {status}"
    )


def run_batch(args):
    """Generate problems and evaluate."""
    seeds = list(range(args.seed_start, args.seed_start + args.problems))

    _safe_print(_c(_C.BOLD, "\n=== SREG Batch Evaluation ===\n"))
    _safe_print(f"  {_c(_C.DIM, 'Template:')} {args.template}")
    _safe_print(f"  {_c(_C.DIM, 'Problemas:')} {args.problems}")
    _safe_print(f"  {_c(_C.DIM, 'Nodos:')} {args.nodes}")
    _safe_print(f"  {_c(_C.DIM, 'Budget:')} {args.budget}")
    _safe_print(f"  {_c(_C.DIM, 'Edge strength:')} {args.edge_strength}")
    _safe_print(f"  {_c(_C.DIM, 'Seeds:')} {seeds[0]}-{seeds[-1]}")
    _safe_print("")

    evaluator = BatchEvaluator()
    problems = evaluator.generate_problems(
        seeds=seeds,
        num_nodes=args.nodes,
        edge_strength=args.edge_strength,
        budget=args.budget,
        template=args.template,
    )

    _safe_print(_c(_C.BOLD, "Evaluando...\n"))
    batch = evaluator.evaluate(problems, seeds=seeds, on_problem=_on_problem)

    # Summary
    s = batch.summary()
    teacher_kl = f"{s['mean_teacher_kl']:.4f}"
    agent_kl = f"{s['mean_agent_kl']:.4f}" if s["mean_agent_kl"] is not None else "N/A"
    random_kl = f"{s['mean_random_kl']:.4f}"

    lines = [
        f"  Problemas:          {s['num_problems']}",
        f"  Submitted:          {s['num_submitted']}/{s['num_problems']}",
        f"  Mejor que random:   {s['num_beats_random']}/{s['num_submitted']}",
        "",
        f"  Mean KL teacher:    {_c(_C.GREEN, teacher_kl)}",
        f"  Mean KL agent:      {_c(_C.BLUE, agent_kl)}",
        f"  Mean KL random:     {_c(_C.RED, random_kl)}",
    ]
    _safe_print("")
    _safe_print(_box("RESULTADOS BATCH", lines, _C.BLUE, width=60))
    _safe_print("")


def run_export(args):
    """Export teacher trajectories to JSONL."""
    seeds = list(range(args.seed_start, args.seed_start + args.problems))

    _safe_print(_c(_C.BOLD, "\n=== SREG Teacher Trajectory Export ===\n"))

    gen = WorldGenTool()
    builder = ProblemBuilder()
    trajectories = []

    for seed in seeds:
        config = WorldGenConfig(
            template_family=args.template,
            seed=seed,
            num_nodes=args.nodes,
            edge_strength=args.edge_strength,
        )
        world = gen.generate(config)
        problem = builder.build(world, budget=args.budget)
        traj = generate_teacher_trajectory(world, problem, seed=seed)
        trajectories.append(traj)

        _safe_print(
            f"  seed={seed:>3}  target={traj.target_node:<20}  "
            f"true={traj.true_state:<8}  steps={len(traj.steps)}"
        )

    out_path = Path(args.export_trajectories)
    export_trajectories(trajectories, out_path)
    _safe_print(f"\n  Exported {len(trajectories)} trajectories to {out_path}\n")


def main():
    parser = argparse.ArgumentParser(description="SREG batch evaluation")
    parser.add_argument("--problems", type=int, default=10, help="Number of problems")
    parser.add_argument("--nodes", type=int, default=6)
    parser.add_argument("--budget", type=int, default=4)
    parser.add_argument("--edge-strength", type=float, default=0.7)
    parser.add_argument("--template", type=str, default="latent_preference",
                        choices=["latent_preference", "causal_chain", "fork_collider"])
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--export-trajectories", type=str, default=None,
                        help="Export teacher trajectories to JSONL (no agent eval)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    else:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("sreg.agent.agent").setLevel(logging.WARNING)

    if args.export_trajectories:
        run_export(args)
    else:
        run_batch(args)


if __name__ == "__main__":
    main()
