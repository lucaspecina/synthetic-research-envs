"""Demo interactivo de SREG en terminal.

Uso:
    python scripts/demo.py
    python scripts/demo.py --seed 42 --nodes 8 --strength 0.3 --budget 5
"""

from __future__ import annotations

import argparse

from sreg.display import (
    show_comparison,
    show_prior,
    show_result,
    show_step,
    show_truth,
    show_validation,
    show_world,
)
from sreg.models.episode import Action, ActionType
from sreg.models.world import NodeType
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_check import WorldCheckTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool


def main() -> None:
    parser = argparse.ArgumentParser(description="SREG demo en terminal")
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--nodes", type=int, default=6)
    parser.add_argument("--strength", type=float, default=0.7)
    parser.add_argument("--states", type=int, default=3)
    parser.add_argument("--budget", type=int, default=4)
    parser.add_argument("--episode-seed", type=int, default=0)
    args = parser.parse_args()

    # 1. Generar mundo
    gen = WorldGenTool()
    world = gen.generate(WorldGenConfig(
        seed=args.seed,
        num_nodes=args.nodes,
        edge_strength=args.strength,
        num_states=args.states,
    ))
    show_world(world)
    print()

    # 2. Validar
    result = WorldCheckTool().check(world)
    show_validation(result.passed, result.failures, result.metrics)
    print()

    # 3. Samplear verdad
    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=args.episode_seed)
    show_truth(world, true_state)
    print()

    # 4. Prior
    prior = solver.posterior("target_outcome")
    show_prior(prior, solver.entropy(prior), true_state["target_outcome"])
    print()

    # 5. Teacher juega paso a paso
    ep = EpisodeGenTool().generate(
        world, EpisodeGenConfig(budget=args.budget, seed=args.episode_seed),
    )
    obs_nodes = list(ep.available_nodes)
    evidence: dict[str, str] = {}

    for step in range(args.budget):
        available = [n for n in obs_nodes if n not in evidence]
        if not available:
            break

        gains = {
            n: solver.information_gain("target_outcome", evidence, n)
            for n in available
        }
        output = solver.optimal_action("target_outcome", evidence, available)
        if output.recommended_action is None:
            print("Entropia ~0, no vale la pena seguir.")
            break

        node = output.recommended_action.node
        evidence[node] = true_state[node]
        post = solver.posterior("target_outcome", evidence)
        h = solver.entropy(post)

        show_step(
            step + 1, node, true_state[node],
            gains, post, h, true_state["target_outcome"],
        )
        print()

    # 6. Resultado teacher
    teacher_post = solver.posterior("target_outcome", evidence)
    teacher_pred = max(teacher_post, key=teacher_post.get)
    show_result(teacher_pred, true_state["target_outcome"])
    print()

    # 7. Comparar con random
    import numpy as np

    rng = np.random.default_rng(42)
    random_order = rng.permutation(obs_nodes).tolist()
    random_ev: dict[str, str] = {}
    for node in random_order[: args.budget]:
        random_ev[node] = true_state[node]

    random_post = solver.posterior("target_outcome", random_ev)
    random_pred = max(random_post, key=random_post.get)

    verifier = VerifierTool()
    t_score = verifier.score(
        agent_posterior=teacher_post, true_posterior=teacher_post,
        budget_used=len(evidence), budget_total=args.budget,
    )
    r_score = verifier.score(
        agent_posterior=random_post, true_posterior=random_post,
        budget_used=len(random_ev), budget_total=args.budget,
    )

    show_comparison(
        teacher_pred, random_pred, true_state["target_outcome"],
        t_score.functional_score, r_score.functional_score,
        solver.entropy(teacher_post), solver.entropy(random_post),
    )


if __name__ == "__main__":
    main()
