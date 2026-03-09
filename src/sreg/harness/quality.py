"""QualitySuite v2: programmatic evaluation of world, task, and generator quality.

Three layers:
  A. WorldQuality  - structural validity (no teacher needed)
  B. TaskQuality   - epistemic quality (multi-rollout, requires teacher)
  C. GeneratorDiversity - batch statistics over many worlds

v2 changes from v1:
  - Layer B uses multi-rollout (K seeds) instead of single-sample
  - Primary belief metric: entropy reduction (sample-independent)
  - Old KL-vs-one-hot metrics renamed to sampled_nll_* (diagnostic only)
  - budget_ratio added for episode design quality
  - useful_bundle tightened (requires entropy reduction + 2 of 3 dimensions)

See WORLD_DESIGN.md "Suite de evaluacion y validacion" for full specification.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field

from sreg.models.task import TaskType
from sreg.models.world import NodeType, World
from sreg.solver.exact_bayes import ExactBayesSolver
from sreg.tools.task_gen import TaskGenTool
from sreg.tools.verifier import VerifierTool
from sreg.tools.world_check import WorldCheckTool

# Default seeds for multi-rollout evaluation
DEFAULT_ROLLOUT_SEEDS = [1, 7, 42, 99, 123]


# ---------------------------------------------------------------------------
# Pydantic metric models
# ---------------------------------------------------------------------------


class WorldQualityMetrics(BaseModel):
    """Layer A: structural quality of a single world."""

    worldcheck_pass: bool
    num_nodes: int
    num_edges: int
    density: float
    treewidth: int
    graph_depth: int
    max_fan_in: int
    max_fan_out: int
    target_reachable_frac: float
    target_entropy: float


class TaskQualityMetrics(BaseModel):
    """Layer B: epistemic quality of tasks derived from a world (multi-rollout)."""

    # Episode design (sample-independent)
    budget_ratio: float = Field(description="budget / observables with path to target")
    prior_entropy: float = Field(description="H(target) without evidence, in bits")
    best_first_ig: float = Field(description="IG of teacher's best first action")
    ig_gap: float = Field(description="max(IG) - min(IG) across observables")

    # Belief quality (averaged over K rollouts)
    num_rollouts: int = Field(description="Number of rollouts used for averaging")
    mean_entropy_reduction: float = Field(
        description="Mean H(prior) - H(teacher_posterior) over rollouts"
    )
    mean_teacher_nll: float = Field(description="Mean -log P_teacher(true_state)")
    mean_prior_nll: float = Field(description="Mean -log P_prior(true_state)")
    mean_nll_improvement: float = Field(
        description="Mean (prior_nll - teacher_nll), >0 means teacher improves"
    )
    mean_random_nll: float = Field(description="Mean -log P_random(true_state)")
    teacher_beats_random_rate: float = Field(
        description="Fraction of rollouts where teacher_nll < random_nll"
    )

    # Task non-degeneration (aggregated over K rollouts)
    nbo_nontrivial_rate: float = Field(
        description="Fraction of rollouts with max(remaining IG) > 0"
    )
    hyp_distinguishable_rate: float = Field(
        description="Fraction of rollouts with min distractor KL > 0.05"
    )

    # Diagnostic (single rollout, for debugging — NOT criteria)
    sampled_nll_teacher: float = Field(
        description="Diagnostic: -log P_teacher(true) for first rollout"
    )
    sampled_nll_prior: float = Field(
        description="Diagnostic: -log P_prior(true) for first rollout"
    )
    teacher_steps_to_stable: int = Field(
        description="Diagnostic: steps until IG < 0.01 in first rollout"
    )

    # Composite
    useful_bundle: bool


class GeneratorDiversityMetrics(BaseModel):
    """Layer C: diversity statistics over a batch of worlds."""

    count: int
    node_count_std: float
    edge_count_std: float
    density_range: float
    depth_range: int
    fan_in_distribution: dict[int, int]
    fan_out_distribution: dict[int, int]
    target_entropy_std: float
    entropy_reduction_std: float
    acceptance_rate: float
    useful_bundle_rate: float


class WorldReport(BaseModel):
    """Combined A+B report for a single world."""

    world_id: str
    seed: int
    world_quality: WorldQualityMetrics
    task_quality: TaskQualityMetrics | None = None
    error: str | None = None


class QualitySuiteReport(BaseModel):
    """Full A+B+C report."""

    worlds: list[WorldReport]
    diversity: GeneratorDiversityMetrics | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entropy(dist: dict[str, float]) -> float:
    """Shannon entropy in bits."""
    return -sum(p * math.log2(p) for p in dist.values() if p > 0)


def _nll(dist: dict[str, float], true_state: str) -> float:
    """Negative log likelihood: -log2 P(true_state)."""
    p = dist.get(true_state, 0.0)
    if p <= 0:
        return 20.0  # cap at ~1e-6 probability
    return -math.log2(p)


# ---------------------------------------------------------------------------
# Layer A: World Quality (unchanged from v1)
# ---------------------------------------------------------------------------

_checker = WorldCheckTool()


def compute_world_quality(world: World) -> WorldQualityMetrics:
    """Compute Layer A metrics for a single world."""
    check_result = _checker.check(world)

    # Build networkx DAG
    dag = nx.DiGraph()
    for node in world.nodes:
        dag.add_node(node.name)
    for edge in world.edges:
        dag.add_edge(edge.from_node, edge.to_node)

    num_nodes = len(world.nodes)
    num_edges = len(world.edges)
    max_possible = num_nodes * (num_nodes - 1) / 2
    density = num_edges / max_possible if max_possible > 0 else 0.0

    # Treewidth from WorldCheck metrics
    treewidth = int(check_result.metrics.get("treewidth_upper_bound", 0))

    # Graph depth = longest path
    try:
        graph_depth = nx.dag_longest_path_length(dag)
    except (nx.NetworkXError, nx.NetworkXUnfeasible):
        graph_depth = 0

    # Fan-in / fan-out
    max_fan_in = max((dag.in_degree(n) for n in dag.nodes()), default=0)
    max_fan_out = max((dag.out_degree(n) for n in dag.nodes()), default=0)

    # Target reachable fraction
    target_nodes = [n for n in world.nodes if n.type == NodeType.TARGET]
    obs_nodes = [n for n in world.nodes if n.type == NodeType.OBSERVABLE]

    if target_nodes and obs_nodes:
        target_name = target_nodes[0].name
        undirected = dag.to_undirected()
        reachable = sum(
            1
            for obs in obs_nodes
            if nx.has_path(undirected, obs.name, target_name)
        )
        target_reachable_frac = reachable / len(obs_nodes)
    else:
        target_reachable_frac = 0.0

    # Target entropy from WorldCheck
    target_entropy = check_result.metrics.get("prior_target_entropy", 0.0)

    return WorldQualityMetrics(
        worldcheck_pass=check_result.passed,
        num_nodes=num_nodes,
        num_edges=num_edges,
        density=round(density, 4),
        treewidth=treewidth,
        graph_depth=graph_depth,
        max_fan_in=max_fan_in,
        max_fan_out=max_fan_out,
        target_reachable_frac=round(target_reachable_frac, 4),
        target_entropy=round(target_entropy, 4),
    )


# ---------------------------------------------------------------------------
# Layer B: Task Quality (v2 — multi-rollout)
# ---------------------------------------------------------------------------

_task_gen = TaskGenTool()
_verifier = VerifierTool()


def compute_task_quality(
    world: World,
    seeds: list[int] | None = None,
) -> TaskQualityMetrics:
    """Compute Layer B metrics for a world using multi-rollout evaluation.

    Args:
        world: The world to evaluate.
        seeds: Seeds for rollouts. Defaults to DEFAULT_ROLLOUT_SEEDS (5 seeds).
    """
    if seeds is None:
        seeds = list(DEFAULT_ROLLOUT_SEEDS)

    solver = ExactBayesSolver(world)
    target_node = next(n for n in world.nodes if n.type == NodeType.TARGET)
    target = target_node.name
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    budget = min(len(obs_nodes), 5)

    # --- Episode design metrics (sample-independent) ---

    # Prior
    prior = solver.posterior(target)
    prior_entropy = _entropy(prior)

    # Budget ratio: budget / observables with path to target
    dag = nx.DiGraph()
    for node in world.nodes:
        dag.add_node(node.name)
    for edge in world.edges:
        dag.add_edge(edge.from_node, edge.to_node)
    undirected = dag.to_undirected()
    relevant_obs = [
        n for n in obs_nodes
        if nx.has_path(undirected, n, target)
    ]
    budget_ratio = budget / len(relevant_obs) if relevant_obs else float("inf")

    # IG for all observables from prior (no evidence)
    igs = []
    for node in obs_nodes:
        ig = solver.information_gain(target, {}, node)
        igs.append(ig)
    best_first_ig = max(igs) if igs else 0.0
    ig_gap = (max(igs) - min(igs)) if igs else 0.0

    # --- Multi-rollout metrics ---
    entropy_reductions: list[float] = []
    teacher_nlls: list[float] = []
    prior_nlls: list[float] = []
    random_nlls: list[float] = []
    teacher_beats_random_count = 0
    nbo_nontrivial_count = 0
    hyp_distinguishable_count = 0

    # Diagnostic from first rollout
    first_sampled_nll_teacher = 0.0
    first_sampled_nll_prior = 0.0
    first_steps_to_stable = budget

    for i, seed in enumerate(seeds):
        true_state = solver.sample_state(seed=seed)
        true_target_state = true_state[target]

        # Teacher trajectory
        _, trajectory = solver.generate_trajectory(
            target=target, available=obs_nodes, budget=budget, seed=seed,
        )

        # Teacher posterior
        teacher_posterior = trajectory[-1].posterior if trajectory else prior
        teacher_entropy = _entropy(teacher_posterior)

        # Entropy reduction
        entropy_reductions.append(prior_entropy - teacher_entropy)

        # NLL metrics
        t_nll = _nll(teacher_posterior, true_target_state)
        p_nll = _nll(prior, true_target_state)
        teacher_nlls.append(t_nll)
        prior_nlls.append(p_nll)

        # Random baseline
        rng = np.random.default_rng(seed + 1000)
        shuffled_obs = list(obs_nodes)
        rng.shuffle(shuffled_obs)
        random_evidence = {n: true_state[n] for n in shuffled_obs[:budget]}
        random_posterior = solver.posterior(target, random_evidence)
        r_nll = _nll(random_posterior, true_target_state)
        random_nlls.append(r_nll)

        if t_nll < r_nll:
            teacher_beats_random_count += 1

        # NBO non-trivial
        bundle = _task_gen.generate_all(
            world, target_node=target, max_budget=budget, seed=seed,
        )
        nbo_task = bundle.tasks[TaskType.NEXT_BEST_OBSERVATION]
        if max(nbo_task.correct_answer.values()) > 0.0:
            nbo_nontrivial_count += 1

        # Hypothesis distinguishable
        hyp_task = bundle.tasks[TaskType.HYPOTHESIS_SELECTION]
        kl_scores = list(hyp_task.correct_answer.values())
        distractor_kls = [kl for kl in kl_scores if kl > 1e-9]
        if distractor_kls and min(distractor_kls) > 0.05:
            hyp_distinguishable_count += 1

        # First rollout diagnostics
        if i == 0:
            first_sampled_nll_teacher = t_nll
            first_sampled_nll_prior = p_nll
            first_steps_to_stable = budget
            for step_idx, step in enumerate(trajectory):
                if step.information_gain < 0.01:
                    first_steps_to_stable = step_idx
                    break

    k = len(seeds)
    mean_entropy_reduction = float(np.mean(entropy_reductions))
    mean_teacher_nll = float(np.mean(teacher_nlls))
    mean_prior_nll = float(np.mean(prior_nlls))
    mean_nll_improvement = float(np.mean(
        [p - t for p, t in zip(prior_nlls, teacher_nlls)]
    ))
    mean_random_nll = float(np.mean(random_nlls))
    teacher_beats_random_rate = teacher_beats_random_count / k
    nbo_nontrivial_rate = nbo_nontrivial_count / k
    hyp_distinguishable_rate = hyp_distinguishable_count / k

    # useful_bundle v2: entropy_reduction > 0.1 AND 2 of 3 dimensions
    dimensions_met = sum([
        nbo_nontrivial_rate > 0.5,
        hyp_distinguishable_rate > 0.5,
        budget_ratio < 0.8,
    ])
    useful_bundle = mean_entropy_reduction > 0.1 and dimensions_met >= 2

    return TaskQualityMetrics(
        budget_ratio=round(budget_ratio, 4),
        prior_entropy=round(prior_entropy, 4),
        best_first_ig=round(best_first_ig, 6),
        ig_gap=round(ig_gap, 6),
        num_rollouts=k,
        mean_entropy_reduction=round(mean_entropy_reduction, 4),
        mean_teacher_nll=round(mean_teacher_nll, 4),
        mean_prior_nll=round(mean_prior_nll, 4),
        mean_nll_improvement=round(mean_nll_improvement, 4),
        mean_random_nll=round(mean_random_nll, 4),
        teacher_beats_random_rate=round(teacher_beats_random_rate, 4),
        nbo_nontrivial_rate=round(nbo_nontrivial_rate, 4),
        hyp_distinguishable_rate=round(hyp_distinguishable_rate, 4),
        sampled_nll_teacher=round(first_sampled_nll_teacher, 4),
        sampled_nll_prior=round(first_sampled_nll_prior, 4),
        teacher_steps_to_stable=first_steps_to_stable,
        useful_bundle=useful_bundle,
    )


# ---------------------------------------------------------------------------
# Layer C: Generator Diversity (v2 — entropy_reduction_std)
# ---------------------------------------------------------------------------


def compute_generator_diversity(
    world_reports: list[WorldReport],
) -> GeneratorDiversityMetrics:
    """Compute Layer C metrics over a batch of WorldReports (with A+B already computed)."""
    if not world_reports:
        return GeneratorDiversityMetrics(
            count=0,
            node_count_std=0.0,
            edge_count_std=0.0,
            density_range=0.0,
            depth_range=0,
            fan_in_distribution={},
            fan_out_distribution={},
            target_entropy_std=0.0,
            entropy_reduction_std=0.0,
            acceptance_rate=0.0,
            useful_bundle_rate=0.0,
        )

    # Extract Layer A metrics
    a_metrics = [r.world_quality for r in world_reports]

    node_counts = [m.num_nodes for m in a_metrics]
    edge_counts = [m.num_edges for m in a_metrics]
    densities = [m.density for m in a_metrics]
    depths = [m.graph_depth for m in a_metrics]
    fan_ins = [m.max_fan_in for m in a_metrics]
    fan_outs = [m.max_fan_out for m in a_metrics]
    entropies = [m.target_entropy for m in a_metrics]
    passed = [m.worldcheck_pass for m in a_metrics]

    # Fan-in/out distributions (histogram)
    fan_in_dist = dict(Counter(fan_ins))
    fan_out_dist = dict(Counter(fan_outs))

    # Entropy reduction std (from Layer B, where available)
    entropy_reductions = [
        r.task_quality.mean_entropy_reduction
        for r in world_reports
        if r.task_quality is not None
    ]
    ent_red_std = float(np.std(entropy_reductions)) if entropy_reductions else 0.0

    # Useful bundle rate
    useful_count = sum(
        1
        for r in world_reports
        if r.task_quality is not None and r.task_quality.useful_bundle
    )
    total_with_tasks = sum(1 for r in world_reports if r.task_quality is not None)
    useful_bundle_rate = (
        useful_count / total_with_tasks if total_with_tasks > 0 else 0.0
    )

    return GeneratorDiversityMetrics(
        count=len(world_reports),
        node_count_std=round(float(np.std(node_counts)), 4),
        edge_count_std=round(float(np.std(edge_counts)), 4),
        density_range=round(max(densities) - min(densities), 4),
        depth_range=max(depths) - min(depths),
        fan_in_distribution=fan_in_dist,
        fan_out_distribution=fan_out_dist,
        target_entropy_std=round(float(np.std(entropies)), 4),
        entropy_reduction_std=round(ent_red_std, 4),
        acceptance_rate=round(sum(passed) / len(passed), 4),
        useful_bundle_rate=round(useful_bundle_rate, 4),
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


def run_quality_suite(
    worlds: list[World],
    rollout_seeds: list[int] | None = None,
) -> QualitySuiteReport:
    """Run the full A+B+C quality suite on a list of worlds.

    Args:
        worlds: List of World objects to evaluate.
        rollout_seeds: Seeds for multi-rollout task quality evaluation.
                       Defaults to DEFAULT_ROLLOUT_SEEDS.
    """
    reports: list[WorldReport] = []
    for world in worlds:
        wq = compute_world_quality(world)

        tq = None
        error = None
        if wq.worldcheck_pass:
            try:
                tq = compute_task_quality(world, seeds=rollout_seeds)
            except Exception as e:
                error = str(e)
        else:
            error = "WorldCheck failed, skipping task quality"

        reports.append(WorldReport(
            world_id=world.id,
            seed=world.seed,
            world_quality=wq,
            task_quality=tq,
            error=error,
        ))

    diversity = compute_generator_diversity(reports)

    # Summary statistics
    total = len(reports)
    passed = sum(1 for r in reports if r.world_quality.worldcheck_pass)
    with_tasks = [r for r in reports if r.task_quality is not None]

    summary: dict[str, Any] = {
        "total_worlds": total,
        "worldcheck_pass_rate": round(passed / total, 4) if total else 0,
    }

    if with_tasks:
        summary["mean_entropy_reduction"] = round(
            float(np.mean([
                r.task_quality.mean_entropy_reduction for r in with_tasks
            ])),
            4,
        )
        summary["mean_nll_improvement"] = round(
            float(np.mean([
                r.task_quality.mean_nll_improvement for r in with_tasks
            ])),
            4,
        )
        summary["teacher_beats_random_rate"] = round(
            float(np.mean([
                r.task_quality.teacher_beats_random_rate for r in with_tasks
            ])),
            4,
        )
        summary["nbo_nontrivial_rate"] = round(
            float(np.mean([
                r.task_quality.nbo_nontrivial_rate for r in with_tasks
            ])),
            4,
        )
        summary["hyp_distinguishable_rate"] = round(
            float(np.mean([
                r.task_quality.hyp_distinguishable_rate for r in with_tasks
            ])),
            4,
        )
        summary["useful_bundle_rate"] = round(
            sum(1 for r in with_tasks if r.task_quality.useful_bundle)
            / len(with_tasks),
            4,
        )
        summary["mean_budget_ratio"] = round(
            float(np.mean([
                r.task_quality.budget_ratio for r in with_tasks
            ])),
            4,
        )

    return QualitySuiteReport(
        worlds=reports,
        diversity=diversity,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

_TARGETS = {
    "worldcheck_pass_rate": (0.85, ">="),
    "mean_entropy_reduction": (0.10, ">="),
    "teacher_beats_random_rate": (0.60, ">="),
    "nbo_nontrivial_rate": (0.70, ">="),
    "hyp_distinguishable_rate": (0.80, ">="),
    "useful_bundle_rate": (0.60, ">="),
    "mean_budget_ratio": (0.80, "<="),
}


def print_quality_report(report: QualitySuiteReport) -> str:
    """Format the quality suite report as a readable ASCII table.

    Returns the formatted string (also prints it).
    """
    lines: list[str] = []
    lines.append("=" * 100)
    lines.append("QUALITY SUITE REPORT (v2 — multi-rollout)")
    lines.append("=" * 100)

    # Per-world table
    header = (
        "{:<18} {:>4} {:>5} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5} {:>5} {:>4}"
    ).format(
        "World", "Seed", "Check", "BudR", "EntRd", "NLLim", "TbRR",
        "NBO", "Hyp", "Bndl", "K",
    )
    lines.append("")
    lines.append(header)
    lines.append("-" * 100)

    for r in report.worlds:
        wq = r.world_quality
        check = "PASS" if wq.worldcheck_pass else "FAIL"
        if r.task_quality:
            tq = r.task_quality
            row = (
                "{:<18} {:>4} {:>5} {:>5.2f} {:>6.3f} {:>6.3f} {:>6.2f}"
                " {:>5.2f} {:>5.2f} {:>5} {:>4}"
            ).format(
                r.world_id[:18],
                r.seed,
                check,
                tq.budget_ratio,
                tq.mean_entropy_reduction,
                tq.mean_nll_improvement,
                tq.teacher_beats_random_rate,
                tq.nbo_nontrivial_rate,
                tq.hyp_distinguishable_rate,
                "Y" if tq.useful_bundle else "N",
                tq.num_rollouts,
            )
        else:
            row = "{:<18} {:>4} {:>5}  -- skipped ({})".format(
                r.world_id[:18], r.seed, check, r.error or "unknown",
            )
        lines.append(row)

    # Summary
    lines.append("")
    lines.append("=" * 100)
    lines.append("SUMMARY")
    lines.append("-" * 100)

    for key, value in report.summary.items():
        target_info = ""
        if key in _TARGETS:
            target_val, target_op = _TARGETS[key]
            met = value >= target_val if target_op == ">=" else value <= target_val
            status = "OK" if met else "BELOW TARGET"
            target_info = "  (target {} {}, {})".format(target_op, target_val, status)
        if isinstance(value, float):
            lines.append("  {:<30} {:>8.4f}{}".format(key, value, target_info))
        else:
            lines.append("  {:<30} {:>8}{}".format(key, value, target_info))

    # Diversity
    if report.diversity and report.diversity.count > 0:
        d = report.diversity
        lines.append("")
        lines.append("GENERATOR DIVERSITY (n={})".format(d.count))
        lines.append("-" * 100)
        lines.append("  {:<30} {:>8.4f}".format("node_count_std", d.node_count_std))
        lines.append("  {:<30} {:>8.4f}".format("edge_count_std", d.edge_count_std))
        lines.append("  {:<30} {:>8.4f}".format("density_range", d.density_range))
        lines.append("  {:<30} {:>8}".format("depth_range", d.depth_range))
        lines.append(
            "  {:<30} {:>8.4f}".format("target_entropy_std", d.target_entropy_std)
        )
        lines.append(
            "  {:<30} {:>8.4f}".format("entropy_reduction_std", d.entropy_reduction_std)
        )
        lines.append(
            "  {:<30} {}".format("fan_in_distribution", d.fan_in_distribution)
        )
        lines.append(
            "  {:<30} {}".format("fan_out_distribution", d.fan_out_distribution)
        )

    lines.append("=" * 100)

    text = "\n".join(lines)
    print(text)
    return text


__all__ = [
    "WorldQualityMetrics",
    "TaskQualityMetrics",
    "GeneratorDiversityMetrics",
    "WorldReport",
    "QualitySuiteReport",
    "compute_world_quality",
    "compute_task_quality",
    "compute_generator_diversity",
    "run_quality_suite",
    "print_quality_report",
]
