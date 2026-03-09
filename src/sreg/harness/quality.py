"""QualitySuite: programmatic evaluation of world, task, and generator quality.

Three layers:
  A. WorldQuality  - structural validity (no teacher needed)
  B. TaskQuality   - epistemic quality (requires teacher)
  C. GeneratorDiversity - batch statistics over many worlds

See WORLD_DESIGN.md "Suite de evaluacion y validacion" for full specification.
"""

from __future__ import annotations

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
    """Layer B: epistemic quality of tasks derived from a world."""

    prior_kl: float = Field(description="KL(true_state || prior)")
    teacher_kl: float = Field(description="KL(true_state || teacher posterior)")
    random_kl: float = Field(description="KL(true_state || random posterior)")
    teacher_beats_prior: bool
    teacher_beats_random: bool
    teacher_random_gap: float
    teacher_steps_to_stable: int
    best_ig: float
    ig_gap: float
    nbo_nontrivial: bool
    hyp_distinguishable: bool
    infer_target_nondegen: bool
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
    ig_gap_std: float
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
# Layer A: World Quality
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

    # Target reachable fraction: what fraction of observables can reach target
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
# Layer B: Task Quality
# ---------------------------------------------------------------------------

_task_gen = TaskGenTool()
_verifier = VerifierTool()


def compute_task_quality(world: World, seed: int = 42) -> TaskQualityMetrics:
    """Compute Layer B metrics for a single world + seed."""
    solver = ExactBayesSolver(world)
    target_node = next(n for n in world.nodes if n.type == NodeType.TARGET)
    target = target_node.name
    obs_nodes = [n.name for n in world.nodes if n.type == NodeType.OBSERVABLE]
    budget = min(len(obs_nodes), 5)

    # Sample true state
    true_state = solver.sample_state(seed=seed)
    true_target_state = true_state[target]

    # Build one-hot for true state
    true_dist = {s: 0.0 for s in target_node.states}
    true_dist[true_target_state] = 1.0

    # Prior
    prior = solver.posterior(target)
    prior_kl = _verifier.kl_divergence(true_dist, prior)

    # Teacher trajectory
    true_state_t, trajectory = solver.generate_trajectory(
        target=target, available=obs_nodes, budget=budget, seed=seed,
    )

    # Teacher final posterior
    if trajectory:
        teacher_posterior = trajectory[-1].posterior
    else:
        teacher_posterior = prior
    teacher_kl = _verifier.kl_divergence(true_dist, teacher_posterior)

    # Teacher steps to stable (IG < 0.01)
    steps_to_stable = budget  # default: never stable
    for i, step in enumerate(trajectory):
        if step.information_gain < 0.01:
            steps_to_stable = i
            break

    # Best IG (first step)
    best_ig = trajectory[0].information_gain if trajectory else 0.0

    # IG gap: compute IG for all observables from prior
    igs = []
    for node in obs_nodes:
        ig = solver.information_gain(target, {}, node)
        igs.append(ig)
    ig_gap = max(igs) - min(igs) if igs else 0.0

    # Random baseline: observe in random order, take final posterior
    rng = np.random.default_rng(seed + 1000)
    shuffled_obs = list(obs_nodes)
    rng.shuffle(shuffled_obs)
    random_evidence: dict[str, str] = {}
    for node_name in shuffled_obs[:budget]:
        random_evidence[node_name] = true_state[node_name]
    random_posterior = solver.posterior(target, random_evidence)
    random_kl = _verifier.kl_divergence(true_dist, random_posterior)

    teacher_beats_prior = teacher_kl <= prior_kl
    teacher_beats_random = teacher_kl <= random_kl
    teacher_random_gap = random_kl - teacher_kl

    # Generate task bundle to check NBO and hypothesis quality
    bundle = _task_gen.generate_all(
        world, target_node=target, max_budget=budget, seed=seed,
    )

    # NBO non-trivial: at least one remaining node has IG > 0
    nbo_task = bundle.tasks[TaskType.NEXT_BEST_OBSERVATION]
    nbo_nontrivial = max(nbo_task.correct_answer.values()) > 0.0

    # Hypothesis distinguishable: min KL between true and nearest distractor > 0.05
    hyp_task = bundle.tasks[TaskType.HYPOTHESIS_SELECTION]
    kl_scores = list(hyp_task.correct_answer.values())
    # The correct hypothesis has KL=0; distractors have KL>0
    distractor_kls = [kl for kl in kl_scores if kl > 1e-9]
    hyp_distinguishable = min(distractor_kls) > 0.05 if distractor_kls else False

    # Infer target non-degenerate: teacher posterior differs from prior
    infer_nondegen_kl = _verifier.kl_divergence(teacher_posterior, prior)
    infer_target_nondegen = infer_nondegen_kl > 0.01

    # Useful bundle: at least 2 of 3 tasks are non-degenerate
    nondegen_count = sum([
        infer_target_nondegen,
        nbo_nontrivial,
        hyp_distinguishable,
    ])
    useful_bundle = nondegen_count >= 2

    return TaskQualityMetrics(
        prior_kl=round(prior_kl, 6),
        teacher_kl=round(teacher_kl, 6),
        random_kl=round(random_kl, 6),
        teacher_beats_prior=teacher_beats_prior,
        teacher_beats_random=teacher_beats_random,
        teacher_random_gap=round(teacher_random_gap, 6),
        teacher_steps_to_stable=steps_to_stable,
        best_ig=round(best_ig, 6),
        ig_gap=round(ig_gap, 6),
        nbo_nontrivial=nbo_nontrivial,
        hyp_distinguishable=hyp_distinguishable,
        infer_target_nondegen=infer_target_nondegen,
        useful_bundle=useful_bundle,
    )


# ---------------------------------------------------------------------------
# Layer C: Generator Diversity
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
            ig_gap_std=0.0,
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

    # IG gap std (from Layer B, where available)
    ig_gaps = [
        r.task_quality.ig_gap
        for r in world_reports
        if r.task_quality is not None
    ]
    ig_gap_std = float(np.std(ig_gaps)) if ig_gaps else 0.0

    # Useful bundle rate
    useful_count = sum(
        1
        for r in world_reports
        if r.task_quality is not None and r.task_quality.useful_bundle
    )
    total_with_tasks = sum(1 for r in world_reports if r.task_quality is not None)
    useful_bundle_rate = useful_count / total_with_tasks if total_with_tasks > 0 else 0.0

    return GeneratorDiversityMetrics(
        count=len(world_reports),
        node_count_std=round(float(np.std(node_counts)), 4),
        edge_count_std=round(float(np.std(edge_counts)), 4),
        density_range=round(max(densities) - min(densities), 4),
        depth_range=max(depths) - min(depths),
        fan_in_distribution=fan_in_dist,
        fan_out_distribution=fan_out_dist,
        target_entropy_std=round(float(np.std(entropies)), 4),
        ig_gap_std=round(ig_gap_std, 4),
        acceptance_rate=round(sum(passed) / len(passed), 4),
        useful_bundle_rate=round(useful_bundle_rate, 4),
    )


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------


def run_quality_suite(
    worlds: list[World],
    seeds: list[int] | None = None,
) -> QualitySuiteReport:
    """Run the full A+B+C quality suite on a list of worlds.

    Args:
        worlds: List of World objects to evaluate.
        seeds: Optional seeds for task quality (one per world).
               Defaults to each world's own seed.
    """
    if seeds is None:
        seeds = [w.seed for w in worlds]

    reports: list[WorldReport] = []
    for world, seed in zip(worlds, seeds):
        wq = compute_world_quality(world)

        tq = None
        error = None
        if wq.worldcheck_pass:
            try:
                tq = compute_task_quality(world, seed=seed)
            except Exception as e:
                error = str(e)
        else:
            error = "WorldCheck failed, skipping task quality"

        reports.append(WorldReport(
            world_id=world.id,
            seed=seed,
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
        summary["teacher_beats_prior_rate"] = round(
            sum(1 for r in with_tasks if r.task_quality.teacher_beats_prior)
            / len(with_tasks),
            4,
        )
        summary["teacher_beats_random_rate"] = round(
            sum(1 for r in with_tasks if r.task_quality.teacher_beats_random)
            / len(with_tasks),
            4,
        )
        summary["nbo_nontrivial_rate"] = round(
            sum(1 for r in with_tasks if r.task_quality.nbo_nontrivial)
            / len(with_tasks),
            4,
        )
        summary["hyp_distinguishable_rate"] = round(
            sum(1 for r in with_tasks if r.task_quality.hyp_distinguishable)
            / len(with_tasks),
            4,
        )
        summary["useful_bundle_rate"] = round(
            sum(1 for r in with_tasks if r.task_quality.useful_bundle)
            / len(with_tasks),
            4,
        )
        summary["mean_teacher_random_gap"] = round(
            float(np.mean([r.task_quality.teacher_random_gap for r in with_tasks])),
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
    "teacher_beats_prior_rate": (0.90, ">="),
    "teacher_beats_random_rate": (0.80, ">="),
    "nbo_nontrivial_rate": (0.70, ">="),
    "hyp_distinguishable_rate": (0.80, ">="),
    "useful_bundle_rate": (0.70, ">="),
    "mean_teacher_random_gap": (0.30, ">="),
}


def print_quality_report(report: QualitySuiteReport) -> str:
    """Format the quality suite report as a readable ASCII table.

    Returns the formatted string (also prints it).
    """
    lines: list[str] = []
    lines.append("=" * 90)
    lines.append("QUALITY SUITE REPORT")
    lines.append("=" * 90)

    # Per-world table
    header = "{:<20} {:>4} {:>5} {:>5} {:>5} {:>6} {:>6} {:>5} {:>4} {:>4}".format(
        "World", "Seed", "Check", "T>P", "T>R", "Gap", "BstIG", "NBO", "Hyp", "Bndl",
    )
    lines.append("")
    lines.append(header)
    lines.append("-" * 90)

    for r in report.worlds:
        wq = r.world_quality
        check = "PASS" if wq.worldcheck_pass else "FAIL"
        if r.task_quality:
            tq = r.task_quality
            row = "{:<20} {:>4} {:>5} {:>5} {:>5} {:>6.3f} {:>6.4f} {:>5} {:>4} {:>4}".format(
                r.world_id[:20],
                r.seed,
                check,
                "Y" if tq.teacher_beats_prior else "N",
                "Y" if tq.teacher_beats_random else "N",
                tq.teacher_random_gap,
                tq.best_ig,
                "Y" if tq.nbo_nontrivial else "N",
                "Y" if tq.hyp_distinguishable else "N",
                "Y" if tq.useful_bundle else "N",
            )
        else:
            row = "{:<20} {:>4} {:>5}  -- skipped ({})".format(
                r.world_id[:20], r.seed, check, r.error or "unknown",
            )
        lines.append(row)

    # Summary
    lines.append("")
    lines.append("=" * 90)
    lines.append("SUMMARY")
    lines.append("-" * 90)

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
        lines.append("-" * 90)
        lines.append("  {:<30} {:>8.4f}".format("node_count_std", d.node_count_std))
        lines.append("  {:<30} {:>8.4f}".format("edge_count_std", d.edge_count_std))
        lines.append("  {:<30} {:>8.4f}".format("density_range", d.density_range))
        lines.append("  {:<30} {:>8}".format("depth_range", d.depth_range))
        lines.append("  {:<30} {:>8.4f}".format("target_entropy_std", d.target_entropy_std))
        lines.append("  {:<30} {:>8.4f}".format("ig_gap_std", d.ig_gap_std))
        lines.append("  {:<30} {}".format("fan_in_distribution", d.fan_in_distribution))
        lines.append("  {:<30} {}".format("fan_out_distribution", d.fan_out_distribution))

    lines.append("=" * 90)

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
