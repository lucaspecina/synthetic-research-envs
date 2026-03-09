"""Batch sweep: systematic comparison of generators/templates across parameter space.

Generates worlds across multiple configurations and runs QualitySuite v2 on each,
producing summary tables that identify regimes with useful information and real strategy.

This is the "last big validation of the formal core" before the project focus shifts
to enriching the case presentation (data, actions, CaseBundle).

Usage:
    python scripts/batch_sweep.py
    python scripts/batch_sweep.py --rollouts 5
    python scripts/batch_sweep.py --quick          # fewer configs for fast iteration
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field

import numpy as np

from sreg.harness.quality import (
    compute_task_quality,
    compute_world_quality,
)
from sreg.tools.world_gen import CustomWorldGenConfig, WorldGenConfig, WorldGenTool
from sreg.world.dag_generators import (
    generate_erdos_renyi,
    generate_layered,
    generate_preferential_attachment,
    generate_spanning_tree,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORLD_SEEDS = [1, 42, 99]
ROLLOUT_SEEDS = [1, 7, 42]

TEMPLATES = ["latent_preference", "causal_chain", "fork_collider"]
NODE_COUNTS = [6, 8, 10, 12]
EDGE_STRENGTHS = [0.3, 0.5, 0.7, 0.9]

# Quick mode uses fewer configs
QUICK_NODE_COUNTS = [6, 10]
QUICK_EDGE_STRENGTHS = [0.5, 0.9]
QUICK_WORLD_SEEDS = [42]


@dataclass
class SweepResult:
    """Aggregated results for one configuration (multiple world seeds)."""

    label: str
    config_type: str  # "template" or "generator"
    num_nodes: int
    edge_strength: float
    num_worlds: int = 0
    worldcheck_pass: int = 0
    # Averaged metrics (only over worlds that passed worldcheck)
    entropy_reductions: list[float] = field(default_factory=list)
    budget_ratios: list[float] = field(default_factory=list)
    teacher_beats_random_rates: list[float] = field(default_factory=list)
    nbo_nontrivial_rates: list[float] = field(default_factory=list)
    hyp_distinguishable_rates: list[float] = field(default_factory=list)
    useful_bundles: list[bool] = field(default_factory=list)
    prior_entropies: list[float] = field(default_factory=list)
    best_first_igs: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _safe_print(text: str) -> None:
    """Print with ASCII-safe encoding for Windows cp1252."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _std(values: list[float]) -> float:
    return float(np.std(values)) if values else 0.0


# ---------------------------------------------------------------------------
# World generation helpers
# ---------------------------------------------------------------------------


def _generate_template_worlds(
    template: str,
    num_nodes: int,
    edge_strength: float,
    world_seeds: list[int],
    world_gen: WorldGenTool,
) -> list:
    """Generate worlds from a template family."""
    worlds = []
    for seed in world_seeds:
        try:
            config = WorldGenConfig(
                template_family=template,
                seed=seed,
                num_nodes=num_nodes,
                edge_strength=edge_strength,
            )
            worlds.append(world_gen.generate(config))
        except Exception as e:
            worlds.append(("error", str(e)))
    return worlds


def _generate_dag_worlds(
    generator: str,
    num_nodes: int,
    edge_strength: float,
    world_seeds: list[int],
    world_gen: WorldGenTool,
) -> list:
    """Generate worlds from a DAG generator."""
    worlds = []
    for seed in world_seeds:
        try:
            if generator == "erdos_renyi":
                spec = generate_erdos_renyi(
                    num_nodes=num_nodes, seed=seed, edge_prob=0.3,
                )
            elif generator == "spanning_tree":
                spec = generate_spanning_tree(
                    num_nodes=num_nodes, seed=seed, extra_edge_prob=0.15,
                )
            elif generator == "preferential_attachment":
                spec = generate_preferential_attachment(
                    num_nodes=num_nodes, seed=seed, num_edges_per_node=2,
                )
            elif generator == "layered":
                # Distribute nodes across layers
                n_layers = max(3, num_nodes // 3)
                spec = generate_layered(
                    num_layers=n_layers,
                    nodes_per_layer=max(2, num_nodes // n_layers),
                    seed=seed,
                    inter_layer_prob=0.5,
                    skip_layer_prob=0.1,
                )
            else:
                raise ValueError(f"Unknown generator: {generator}")

            config = CustomWorldGenConfig(
                dag_spec=spec, edge_strength=edge_strength, seed=seed,
            )
            worlds.append(world_gen.generate_custom(config))
        except Exception as e:
            worlds.append(("error", str(e)))
    return worlds


# ---------------------------------------------------------------------------
# Sweep runner
# ---------------------------------------------------------------------------


def run_sweep(
    world_seeds: list[int],
    rollout_seeds: list[int],
    node_counts: list[int],
    edge_strengths: list[float],
) -> list[SweepResult]:
    """Run the full parameter sweep."""
    world_gen = WorldGenTool()
    results: list[SweepResult] = []
    total_configs = len(TEMPLATES) * len(node_counts) * len(edge_strengths) + \
        4 * len(node_counts) * len(edge_strengths)
    config_num = 0

    # --- Templates ---
    for template in TEMPLATES:
        for num_nodes in node_counts:
            for es in edge_strengths:
                config_num += 1
                label = f"{template[:12]}"
                _safe_print(
                    f"  [{config_num}/{total_configs}] {label} "
                    f"n={num_nodes} es={es}"
                )

                sr = SweepResult(
                    label=template,
                    config_type="template",
                    num_nodes=num_nodes,
                    edge_strength=es,
                )

                worlds = _generate_template_worlds(
                    template, num_nodes, es, world_seeds, world_gen,
                )

                for w in worlds:
                    sr.num_worlds += 1
                    if isinstance(w, tuple):
                        sr.errors.append(w[1])
                        continue

                    wq = compute_world_quality(w)
                    if wq.worldcheck_pass:
                        sr.worldcheck_pass += 1
                        try:
                            tq = compute_task_quality(w, seeds=rollout_seeds)
                            sr.entropy_reductions.append(tq.mean_entropy_reduction)
                            sr.budget_ratios.append(tq.budget_ratio)
                            sr.teacher_beats_random_rates.append(
                                tq.teacher_beats_random_rate
                            )
                            sr.nbo_nontrivial_rates.append(tq.nbo_nontrivial_rate)
                            sr.hyp_distinguishable_rates.append(
                                tq.hyp_distinguishable_rate
                            )
                            sr.useful_bundles.append(tq.useful_bundle)
                            sr.prior_entropies.append(tq.prior_entropy)
                            sr.best_first_igs.append(tq.best_first_ig)
                        except Exception as e:
                            sr.errors.append(str(e))

                results.append(sr)

    # --- DAG generators ---
    generators = ["erdos_renyi", "spanning_tree", "preferential_attachment", "layered"]
    for gen in generators:
        for num_nodes in node_counts:
            for es in edge_strengths:
                config_num += 1
                _safe_print(
                    f"  [{config_num}/{total_configs}] {gen[:16]} "
                    f"n={num_nodes} es={es}"
                )

                sr = SweepResult(
                    label=gen,
                    config_type="generator",
                    num_nodes=num_nodes,
                    edge_strength=es,
                )

                worlds = _generate_dag_worlds(
                    gen, num_nodes, es, world_seeds, world_gen,
                )

                for w in worlds:
                    sr.num_worlds += 1
                    if isinstance(w, tuple):
                        sr.errors.append(w[1])
                        continue

                    wq = compute_world_quality(w)
                    if wq.worldcheck_pass:
                        sr.worldcheck_pass += 1
                        try:
                            tq = compute_task_quality(w, seeds=rollout_seeds)
                            sr.entropy_reductions.append(tq.mean_entropy_reduction)
                            sr.budget_ratios.append(tq.budget_ratio)
                            sr.teacher_beats_random_rates.append(
                                tq.teacher_beats_random_rate
                            )
                            sr.nbo_nontrivial_rates.append(tq.nbo_nontrivial_rate)
                            sr.hyp_distinguishable_rates.append(
                                tq.hyp_distinguishable_rate
                            )
                            sr.useful_bundles.append(tq.useful_bundle)
                            sr.prior_entropies.append(tq.prior_entropy)
                            sr.best_first_igs.append(tq.best_first_ig)
                        except Exception as e:
                            sr.errors.append(str(e))

                results.append(sr)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_sweep_report(results: list[SweepResult]) -> str:
    """Format sweep results as readable ASCII tables."""
    lines: list[str] = []
    lines.append("=" * 120)
    lines.append("BATCH SWEEP REPORT — Generator/Template Comparison")
    lines.append("=" * 120)

    # --- Table 1: Per-config summary ---
    lines.append("")
    lines.append("PER-CONFIGURATION SUMMARY")
    lines.append(
        "{:<20} {:>3} {:>4} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5} {:>5} {:>5} {:>5}"
        .format(
            "Generator/Template", "N", "ES", "WCpas", "EntRd", "BudR",
            "TbRR", "NBO", "Hyp", "Bndl", "PriEn", "1stIG",
        )
    )
    lines.append("-" * 120)

    for sr in results:
        n_eval = len(sr.entropy_reductions)
        wc_rate = sr.worldcheck_pass / sr.num_worlds if sr.num_worlds else 0

        if n_eval > 0:
            ent_rd = _mean(sr.entropy_reductions)
            bud_r = _mean(sr.budget_ratios)
            tb_rr = _mean(sr.teacher_beats_random_rates)
            nbo = _mean(sr.nbo_nontrivial_rates)
            hyp = _mean(sr.hyp_distinguishable_rates)
            bndl = sum(sr.useful_bundles) / len(sr.useful_bundles)
            pri_en = _mean(sr.prior_entropies)
            first_ig = _mean(sr.best_first_igs)

            row = (
                "{:<20} {:>3} {:>4.1f} {:>5.0%} {:>6.3f} {:>6.2f} {:>6.2f}"
                " {:>5.2f} {:>5.2f} {:>5.0%} {:>5.2f} {:>5.3f}"
            ).format(
                sr.label[:20], sr.num_nodes, sr.edge_strength,
                wc_rate, ent_rd, bud_r, tb_rr, nbo, hyp, bndl, pri_en, first_ig,
            )
        else:
            row = "{:<20} {:>3} {:>4.1f} {:>5.0%}  -- no evaluable worlds --".format(
                sr.label[:20], sr.num_nodes, sr.edge_strength, wc_rate,
            )
        lines.append(row)

    # --- Table 2: Aggregated by generator/template (across all params) ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("AGGREGATED BY GENERATOR/TEMPLATE (across all node counts and edge strengths)")
    lines.append(
        "{:<24} {:>5} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5} {:>5} {:>5}"
        .format(
            "Generator/Template", "Wrlds", "WCpas", "EntRd", "BudR",
            "TbRR", "NBO", "Hyp", "Bndl", "1stIG",
        )
    )
    lines.append("-" * 120)

    # Group by label
    from collections import defaultdict
    groups: dict[str, list[SweepResult]] = defaultdict(list)
    for sr in results:
        groups[sr.label].append(sr)

    for label in sorted(groups.keys()):
        srs = groups[label]
        total_worlds = sum(s.num_worlds for s in srs)
        total_pass = sum(s.worldcheck_pass for s in srs)
        all_ent = [v for s in srs for v in s.entropy_reductions]
        all_bud = [v for s in srs for v in s.budget_ratios]
        all_tbr = [v for s in srs for v in s.teacher_beats_random_rates]
        all_nbo = [v for s in srs for v in s.nbo_nontrivial_rates]
        all_hyp = [v for s in srs for v in s.hyp_distinguishable_rates]
        all_bndl = [v for s in srs for v in s.useful_bundles]
        all_ig = [v for s in srs for v in s.best_first_igs]

        if all_ent:
            row = (
                "{:<24} {:>5} {:>5.0%} {:>6.3f} {:>6.2f} {:>6.2f}"
                " {:>5.2f} {:>5.2f} {:>5.0%} {:>5.3f}"
            ).format(
                label[:24],
                total_worlds,
                total_pass / total_worlds if total_worlds else 0,
                _mean(all_ent), _mean(all_bud), _mean(all_tbr),
                _mean(all_nbo), _mean(all_hyp),
                sum(all_bndl) / len(all_bndl) if all_bndl else 0,
                _mean(all_ig),
            )
        else:
            row = "{:<24} {:>5} {:>5.0%}  -- no evaluable worlds --".format(
                label[:24], total_worlds,
                total_pass / total_worlds if total_worlds else 0,
            )
        lines.append(row)

    # --- Table 3: Effect of num_nodes (across all generators) ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("EFFECT OF NUM_NODES (across all generators/templates)")
    lines.append(
        "{:>5} {:>5} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5} {:>5}"
        .format("Nodes", "Wrlds", "WCpas", "EntRd", "BudR", "TbRR", "NBO", "Hyp", "Bndl")
    )
    lines.append("-" * 120)

    node_groups: dict[int, list[SweepResult]] = defaultdict(list)
    for sr in results:
        node_groups[sr.num_nodes].append(sr)

    for nn in sorted(node_groups.keys()):
        srs = node_groups[nn]
        total_worlds = sum(s.num_worlds for s in srs)
        total_pass = sum(s.worldcheck_pass for s in srs)
        all_ent = [v for s in srs for v in s.entropy_reductions]
        all_bud = [v for s in srs for v in s.budget_ratios]
        all_tbr = [v for s in srs for v in s.teacher_beats_random_rates]
        all_nbo = [v for s in srs for v in s.nbo_nontrivial_rates]
        all_hyp = [v for s in srs for v in s.hyp_distinguishable_rates]
        all_bndl = [v for s in srs for v in s.useful_bundles]

        row = (
            "{:>5} {:>5} {:>5.0%} {:>6.3f} {:>6.2f} {:>6.2f}"
            " {:>5.2f} {:>5.2f} {:>5.0%}"
        ).format(
            nn, total_worlds,
            total_pass / total_worlds if total_worlds else 0,
            _mean(all_ent), _mean(all_bud), _mean(all_tbr),
            _mean(all_nbo), _mean(all_hyp),
            sum(all_bndl) / len(all_bndl) if all_bndl else 0,
        )
        lines.append(row)

    # --- Table 4: Effect of edge_strength (across all generators) ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("EFFECT OF EDGE_STRENGTH (across all generators/templates)")
    lines.append(
        "{:>5} {:>5} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5} {:>5}"
        .format("ES", "Wrlds", "WCpas", "EntRd", "BudR", "TbRR", "NBO", "Hyp", "Bndl")
    )
    lines.append("-" * 120)

    es_groups: dict[float, list[SweepResult]] = defaultdict(list)
    for sr in results:
        es_groups[sr.edge_strength].append(sr)

    for es in sorted(es_groups.keys()):
        srs = es_groups[es]
        total_worlds = sum(s.num_worlds for s in srs)
        total_pass = sum(s.worldcheck_pass for s in srs)
        all_ent = [v for s in srs for v in s.entropy_reductions]
        all_bud = [v for s in srs for v in s.budget_ratios]
        all_tbr = [v for s in srs for v in s.teacher_beats_random_rates]
        all_nbo = [v for s in srs for v in s.nbo_nontrivial_rates]
        all_hyp = [v for s in srs for v in s.hyp_distinguishable_rates]
        all_bndl = [v for s in srs for v in s.useful_bundles]

        row = (
            "{:>5.1f} {:>5} {:>5.0%} {:>6.3f} {:>6.2f} {:>6.2f}"
            " {:>5.2f} {:>5.2f} {:>5.0%}"
        ).format(
            es, total_worlds,
            total_pass / total_worlds if total_worlds else 0,
            _mean(all_ent), _mean(all_bud), _mean(all_tbr),
            _mean(all_nbo), _mean(all_hyp),
            sum(all_bndl) / len(all_bndl) if all_bndl else 0,
        )
        lines.append(row)

    # --- Table 5: Best configurations (highest useful_bundle rate) ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("TOP 15 CONFIGURATIONS (by useful_bundle rate, min 2 evaluable worlds)")
    lines.append(
        "{:<20} {:>3} {:>4} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5} {:>5}"
        .format(
            "Generator/Template", "N", "ES", "Bndl", "EntRd", "BudR",
            "TbRR", "NBO", "Hyp", "1stIG",
        )
    )
    lines.append("-" * 120)

    scored = []
    for sr in results:
        n_eval = len(sr.useful_bundles)
        if n_eval >= 2:
            bndl_rate = sum(sr.useful_bundles) / n_eval
            scored.append((bndl_rate, sr))

    scored.sort(key=lambda x: (-x[0], -_mean(x[1].entropy_reductions)))
    for bndl_rate, sr in scored[:15]:
        row = (
            "{:<20} {:>3} {:>4.1f} {:>5.0%} {:>6.3f} {:>6.2f} {:>6.2f}"
            " {:>5.2f} {:>5.2f} {:>5.3f}"
        ).format(
            sr.label[:20], sr.num_nodes, sr.edge_strength,
            bndl_rate,
            _mean(sr.entropy_reductions), _mean(sr.budget_ratios),
            _mean(sr.teacher_beats_random_rates),
            _mean(sr.nbo_nontrivial_rates),
            _mean(sr.hyp_distinguishable_rates),
            _mean(sr.best_first_igs),
        )
        lines.append(row)

    # --- Table 6: Worst configurations ---
    lines.append("")
    lines.append("BOTTOM 10 CONFIGURATIONS (lowest useful_bundle rate, min 1 world)")
    lines.append(
        "{:<20} {:>3} {:>4} {:>5} {:>6} {:>6} {:>6} {:>5} {:>5}"
        .format(
            "Generator/Template", "N", "ES", "Bndl", "EntRd", "BudR",
            "TbRR", "NBO", "Hyp",
        )
    )
    lines.append("-" * 120)

    # Include configs with 0 evaluable worlds (worldcheck failures)
    all_scored = []
    for sr in results:
        n_eval = len(sr.useful_bundles)
        if n_eval >= 1:
            bndl_rate = sum(sr.useful_bundles) / n_eval
        else:
            bndl_rate = -1  # no evaluable worlds = worst
        all_scored.append((bndl_rate, sr))

    all_scored.sort(key=lambda x: (x[0], _mean(x[1].entropy_reductions)))
    for bndl_rate, sr in all_scored[:10]:
        n_eval = len(sr.useful_bundles)
        if n_eval > 0:
            row = (
                "{:<20} {:>3} {:>4.1f} {:>5.0%} {:>6.3f} {:>6.2f} {:>6.2f}"
                " {:>5.2f} {:>5.2f}"
            ).format(
                sr.label[:20], sr.num_nodes, sr.edge_strength,
                bndl_rate,
                _mean(sr.entropy_reductions), _mean(sr.budget_ratios),
                _mean(sr.teacher_beats_random_rates),
                _mean(sr.nbo_nontrivial_rates),
                _mean(sr.hyp_distinguishable_rates),
            )
        else:
            wc = sr.worldcheck_pass / sr.num_worlds if sr.num_worlds else 0
            row = "{:<20} {:>3} {:>4.1f}  -- 0% worldcheck pass ({:.0%}) --".format(
                sr.label[:20], sr.num_nodes, sr.edge_strength, wc,
            )
        lines.append(row)

    # --- Key findings ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("KEY METRICS LEGEND")
    lines.append("-" * 120)
    lines.append("  WCpas = WorldCheck pass rate")
    lines.append("  EntRd = mean entropy reduction (target >= 0.10)")
    lines.append("  BudR  = budget ratio, budget/relevant_obs (target <= 0.80)")
    lines.append("  TbRR  = teacher beats random rate (target >= 0.60)")
    lines.append("  NBO   = NBO non-trivial rate (target >= 0.70)")
    lines.append("  Hyp   = hypothesis distinguishable rate (target >= 0.80)")
    lines.append("  Bndl  = useful_bundle rate (target >= 0.60)")
    lines.append("  PriEn = prior entropy (bits)")
    lines.append("  1stIG = best first-step information gain")
    lines.append("=" * 120)

    text = "\n".join(lines)
    _safe_print(text)
    return text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Batch sweep of generators/templates")
    parser.add_argument("--rollouts", type=int, default=3, help="Rollout seeds per world")
    parser.add_argument("--quick", action="store_true", help="Quick mode (fewer configs)")
    args = parser.parse_args()

    if args.quick:
        node_counts = QUICK_NODE_COUNTS
        edge_strengths = QUICK_EDGE_STRENGTHS
        world_seeds = QUICK_WORLD_SEEDS
    else:
        node_counts = NODE_COUNTS
        edge_strengths = EDGE_STRENGTHS
        world_seeds = WORLD_SEEDS

    rollout_seeds = list(range(1, args.rollouts + 1))

    total_configs = (len(TEMPLATES) + 4) * len(node_counts) * len(edge_strengths)
    total_worlds = total_configs * len(world_seeds)

    _safe_print(f"Batch sweep: {total_configs} configs x {len(world_seeds)} seeds "
                f"= {total_worlds} worlds, {args.rollouts} rollouts each")
    _safe_print("")

    t0 = time.time()
    results = run_sweep(world_seeds, rollout_seeds, node_counts, edge_strengths)
    elapsed = time.time() - t0

    _safe_print("")
    _safe_print(f"Sweep completed in {elapsed:.1f}s")
    _safe_print("")

    print_sweep_report(results)


if __name__ == "__main__":
    main()
