"""Dataset generation: SRC -> HuggingFace Dataset for SregEnv.

Generates complete SRCs using SREG tools (no LLM needed) and packages
them as HuggingFace Dataset rows compatible with SregEnv.

Usage:
    from sreg.training.dataset import generate_dataset
    ds = generate_dataset(n=50, seed=0)
    # Then pass to SregEnv: env = SregEnv(dataset=ds)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from datasets import Dataset

from sreg.models.research_problem import ResearchProblem
from sreg.models.task import TaskBundle, TaskType
from sreg.models.world import World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.episode_gen import EpisodeGenConfig, EpisodeGenTool
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.task_gen import TaskGenTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool
from sreg.training.prompts import SYSTEM_PROMPT, render_case_prompt

logger = logging.getLogger(__name__)

# Eval types to include (all 9 supported types)
_ALL_EVAL_TYPES: list[TaskType] = [
    TaskType.INFER_TARGET,
    TaskType.CAUSAL_EFFECT,
    TaskType.INFER_LATENT_CAUSE,
    TaskType.HYPOTHESIS_SELECTION,
    TaskType.NEXT_BEST_OBSERVATION,
    TaskType.BEST_INTERVENTION,
    TaskType.COMPARE_INTERVENTIONS,
    TaskType.SHOULD_CONDITION,
    TaskType.ADJUSTMENT_SET,
]


def src_to_rows(
    world: World,
    problem: ResearchProblem,
    bundle: TaskBundle,
    true_state: dict[str, str],
    eval_types: list[TaskType] | None = None,
) -> list[dict[str, Any]]:
    """Convert a single SRC into dataset rows (one per task/eval_type).

    Args:
        world: Complete world model (with CPDs).
        problem: Research problem (what the agent sees).
        bundle: Task bundle generated from the world.
        true_state: Ground truth values for all nodes.
        eval_types: Which eval types to include. None = all available.

    Returns:
        List of dataset row dicts ready for HF Dataset.
    """
    eg = EpisodeGenTool()
    prompt_text = render_case_prompt(problem)
    data_assets = [a.model_dump() for a in problem.data_assets] if problem.data_assets else []

    rows = []
    target_types = eval_types or _ALL_EVAL_TYPES

    for task_type in target_types:
        task = bundle.tasks.get(task_type)
        if task is None:
            continue

        # Generate a fresh episode for each task
        episode = eg.generate(
            world,
            EpisodeGenConfig(budget=problem.budget, seed=hash(task.id) % (2**31)),
            true_state=true_state,
            available_actions=problem.available_actions,
        )

        row = {
            "prompt": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
            "info": json.dumps(
                {
                    "world_json": world.model_dump_json(),
                    "episode_json": episode.model_dump_json(),
                    "true_state": true_state,
                    "eval_type": task.type.value,
                    "correct_answer": task.correct_answer,
                    "data_assets": data_assets,
                }
            ),
        }
        rows.append(row)

    return rows


def generate_src(
    seed: int,
    num_nodes: int = 8,
    budget: int = 5,
) -> tuple[World, ResearchProblem, TaskBundle, dict[str, str]]:
    """Generate a single complete SRC programmatically (no LLM needed).

    Returns:
        Tuple of (world, problem, bundle, true_state).
    """
    wg = WorldGenTool()
    world = wg.generate(WorldGenConfig(num_nodes=num_nodes, seed=seed))

    solver = ExactBayesSolver(world)
    true_state = solver.sample_state(seed=seed)

    pb = ProblemBuilder()
    problem = pb.build(world, budget=budget, rich_actions=True)

    tg = TaskGenTool()
    bundle = tg.generate_all(world, max_budget=budget, seed=seed)

    return world, problem, bundle, true_state


def generate_dataset(
    n: int = 10,
    seed: int = 0,
    num_nodes: int = 8,
    budget: int = 5,
    eval_types: list[TaskType] | None = None,
) -> Dataset:
    """Generate a training dataset with N SRCs.

    Each SRC produces multiple rows (one per eval_type). Total rows
    will be N * (number of eval types generated per SRC).

    Args:
        n: Number of SRCs to generate.
        seed: Base seed (each SRC uses seed + i).
        num_nodes: Nodes per world.
        budget: Agent budget per episode.
        eval_types: Which eval types to include. None = all available.

    Returns:
        HuggingFace Dataset ready for SregEnv.
    """
    all_rows: list[dict[str, Any]] = []

    for i in range(n):
        src_seed = seed + i
        try:
            world, problem, bundle, true_state = generate_src(
                seed=src_seed, num_nodes=num_nodes, budget=budget
            )
            rows = src_to_rows(world, problem, bundle, true_state, eval_types=eval_types)
            all_rows.extend(rows)
            logger.info(
                "SRC %d (seed=%d): %d rows, types=%s",
                i,
                src_seed,
                len(rows),
                [r["info"] for r in rows]
                if False
                else [json.loads(r["info"])["eval_type"] for r in rows],
            )
        except Exception:
            logger.exception("Failed to generate SRC %d (seed=%d)", i, src_seed)
            continue

    if not all_rows:
        raise RuntimeError(f"No SRCs generated successfully from {n} attempts")

    ds = Dataset.from_list(all_rows)
    logger.info("Dataset: %d rows from %d SRCs", len(ds), n)
    return ds
