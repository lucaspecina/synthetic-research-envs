"""Batch evaluation: run agent + teacher across multiple problems, collect metrics."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sreg.agent.agent import AgentResult, AgentSolver
from sreg.harness.trajectory import generate_teacher_trajectory
from sreg.models.research_problem import ResearchProblem
from sreg.models.world import World
from sreg.tools.problem_builder import ProblemBuilder
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_gen import WorldGenConfig, WorldGenTool

logger = logging.getLogger(__name__)


@dataclass
class ProblemResult:
    """Result for a single problem in the batch."""

    world_id: str
    seed: int
    num_nodes: int
    edge_strength: float
    target_node: str
    true_state: str
    budget: int

    # Teacher
    teacher_kl: float = 0.0
    teacher_steps: int = 0

    # Agent
    agent_kl: float | None = None
    agent_steps: int = 0
    agent_submitted: bool = False

    # Random baseline
    random_kl: float = 0.0

    @property
    def agent_beats_random(self) -> bool | None:
        if self.agent_kl is None:
            return None
        return self.agent_kl < self.random_kl


@dataclass
class BatchResult:
    """Aggregated results for a batch evaluation."""

    results: list[ProblemResult] = field(default_factory=list)

    @property
    def num_problems(self) -> int:
        return len(self.results)

    @property
    def num_submitted(self) -> int:
        return sum(1 for r in self.results if r.agent_submitted)

    @property
    def num_beats_random(self) -> int:
        return sum(1 for r in self.results if r.agent_beats_random is True)

    @property
    def mean_agent_kl(self) -> float | None:
        submitted = [r.agent_kl for r in self.results if r.agent_kl is not None]
        return sum(submitted) / len(submitted) if submitted else None

    @property
    def mean_teacher_kl(self) -> float:
        return sum(r.teacher_kl for r in self.results) / len(self.results)

    @property
    def mean_random_kl(self) -> float:
        return sum(r.random_kl for r in self.results) / len(self.results)

    def summary(self) -> dict:
        """Return a summary dict suitable for display or export."""
        return {
            "num_problems": self.num_problems,
            "num_submitted": self.num_submitted,
            "num_beats_random": self.num_beats_random,
            "mean_teacher_kl": round(self.mean_teacher_kl, 4) if self.results else None,
            "mean_agent_kl": (
                round(self.mean_agent_kl, 4) if self.mean_agent_kl is not None else None
            ),
            "mean_random_kl": round(self.mean_random_kl, 4) if self.results else None,
        }


class BatchEvaluator:
    """Generate problems and evaluate agent vs teacher."""

    def __init__(self, agent: AgentSolver | None = None):
        self._agent = agent or AgentSolver(max_iterations=15)
        self._world_gen = WorldGenTool()
        self._problem_builder = ProblemBuilder()
        self._verifier = VerifierTool()

    def generate_problems(
        self,
        seeds: list[int],
        num_nodes: int = 6,
        edge_strength: float = 0.7,
        budget: int = 4,
        template: str = "latent_preference",
    ) -> list[tuple[World, ResearchProblem]]:
        """Generate worlds + problems programmatically (no LLM calls)."""
        problems = []
        for seed in seeds:
            config = WorldGenConfig(
                template_family=template,
                seed=seed,
                num_nodes=num_nodes,
                edge_strength=edge_strength,
            )
            world = self._world_gen.generate(config)
            problem = self._problem_builder.build(world, budget=budget)
            problems.append((world, problem))
        return problems

    def evaluate(
        self,
        problems: list[tuple[World, ResearchProblem]],
        seeds: list[int] | None = None,
        on_problem: callable | None = None,
    ) -> BatchResult:
        """Run agent + teacher on each problem and collect metrics.

        Args:
            problems: List of (world, problem) tuples.
            seeds: Seeds for sampling true state per problem. Defaults to [0, 1, 2, ...].
            on_problem: Optional callback(index, total, problem_result) for progress.
        """
        if seeds is None:
            seeds = list(range(len(problems)))

        batch = BatchResult()

        for i, ((world, problem), seed) in enumerate(zip(problems, seeds)):
            logger.info(f"Evaluating problem {i + 1}/{len(problems)} (seed={seed})")

            pr = self._evaluate_one(world, problem, seed)

            batch.results.append(pr)

            if on_problem:
                on_problem(i, len(problems), pr)

        return batch

    def _evaluate_one(
        self, world: World, problem: ResearchProblem, seed: int
    ) -> ProblemResult:
        """Evaluate a single problem."""
        # Teacher
        traj = generate_teacher_trajectory(world, problem, seed=seed)

        pr = ProblemResult(
            world_id=world.id,
            seed=seed,
            num_nodes=len(world.nodes),
            edge_strength=world.difficulty.edge_density if world.difficulty else 0.0,
            target_node=problem.target_node,
            true_state=traj.true_state,
            budget=problem.budget,
            teacher_kl=0.0,  # Teacher submits exact posterior
            teacher_steps=len(traj.steps),
        )

        # Random baseline
        uniform = {s: 1.0 / len(problem.target_states) for s in problem.target_states}
        random_score = self._verifier.score(
            agent_posterior=uniform,
            true_posterior=traj.final_posterior,
            budget_used=0,
            budget_total=problem.budget,
        )
        pr.random_kl = random_score.functional_score

        # Agent
        try:
            agent_result: AgentResult = self._agent.solve(world, problem, seed=seed)

            pr.agent_steps = agent_result.budget_used
            pr.agent_submitted = agent_result.submitted_answer is not None

            if agent_result.score is not None:
                pr.agent_kl = agent_result.score.functional_score
        except Exception as e:
            logger.error(f"Agent failed on {world.id}: {e}")
            pr.agent_submitted = False

        return pr


__all__ = ["BatchEvaluator", "BatchResult", "ProblemResult"]
