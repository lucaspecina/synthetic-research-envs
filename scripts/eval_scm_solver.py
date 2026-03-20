"""Rigorous evaluation of SCMSolver quality.

Tests against analytical ground truth where possible (Linear Gaussian),
measures variance across seeds, and reports rejection sampling diagnostics.

Measures:
1. Posterior accuracy vs analytical (Linear Gaussian closed-form)
2. Interventional with evidence (rejection sampling path)
3. IG ranking stability across seeds (mean +/- std)
4. Rejection sampling acceptance rate diagnostics
5. Scale behavior: timing + correctness as graph grows

Run: python scripts/eval_scm_solver.py
"""

from __future__ import annotations

import time

import numpy as np
from scipy import stats

from sreg.solver.scm_solver import SCMSolver
from sreg.world.scm import SCMWorld, VariableMeta


# ------------------------------------------------------------------
# Test worlds
# ------------------------------------------------------------------


def make_linear_gaussian() -> SCMWorld:
    """A -> B -> C. Pure linear Gaussian — has analytical posterior.

    A ~ N(10, 2)
    B = 2*A + N(0, 1)    => B|A ~ N(2*A, 1)
    C = 0.5*B + N(0, 0.5) => C|B ~ N(0.5*B, 0.5)
    """
    return SCMWorld(
        graph={"A": [], "B": ["A"], "C": ["B"]},
        equations={
            "A": lambda p, rng: rng.normal(10, 2),
            "B": lambda p, rng: 2 * p["A"] + rng.normal(0, 1),
            "C": lambda p, rng: 0.5 * p["B"] + rng.normal(0, 0.5),
        },
        variable_meta={
            "A": VariableMeta(unit="u", range=(0, 30)),
            "B": VariableMeta(unit="u", range=(0, 50)),
            "C": VariableMeta(unit="u", range=(0, 30)),
        },
    )


def make_chain(n: int) -> SCMWorld:
    """X0 -> X1 -> ... -> X_{n-1}. Linear chain with additive noise."""
    graph = {"X0": []}
    equations = {"X0": lambda p, rng: rng.normal(10, 2)}
    meta = {"X0": VariableMeta(unit="u", range=(0, 20))}
    for i in range(1, n):
        parent = f"X{i-1}"
        graph[f"X{i}"] = [parent]
        equations[f"X{i}"] = (
            lambda p, rng, par=parent: 0.8 * p[par] + rng.normal(0, 1)
        )
        meta[f"X{i}"] = VariableMeta(unit="u", range=(0, 30))
    return SCMWorld(graph=graph, equations=equations, variable_meta=meta)


def make_fork(n_children: int) -> SCMWorld:
    """Z -> C0, Z -> C1, ..., Z -> Cn. Common cause structure."""
    graph = {"Z": []}
    equations = {"Z": lambda p, rng: rng.normal(5, 2)}
    for i in range(n_children):
        name = f"C{i}"
        graph[name] = ["Z"]
        coef = 1.0 + 0.5 * i
        equations[name] = (
            lambda p, rng, c=coef: c * p["Z"] + rng.normal(0, 1)
        )
    return SCMWorld(graph=graph, equations=equations)


def make_diamond() -> SCMWorld:
    """A -> B, A -> C, B -> D, C -> D. Classic diamond."""
    return SCMWorld(
        graph={"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]},
        equations={
            "A": lambda p, rng: rng.normal(0, 1),
            "B": lambda p, rng: 2 * p["A"] + rng.normal(0, 0.5),
            "C": lambda p, rng: -p["A"] + rng.normal(0, 0.5),
            "D": lambda p, rng: p["B"] + 0.5 * p["C"] + rng.normal(0, 0.3),
        },
    )


# ------------------------------------------------------------------
# Analytical posteriors for Linear Gaussian
# ------------------------------------------------------------------


def analytical_posterior_b_given_a(a_val: float) -> tuple[float, float]:
    """P(B | A=a) for the linear Gaussian model.

    B = 2*A + eps, eps ~ N(0, 1)
    => B | A=a ~ N(2*a, 1)
    """
    return 2 * a_val, 1.0


def analytical_posterior_c_given_b(b_val: float) -> tuple[float, float]:
    """P(C | B=b) for the linear Gaussian model.

    C = 0.5*B + eps, eps ~ N(0, 0.5)
    => C | B=b ~ N(0.5*b, 0.5)
    """
    return 0.5 * b_val, 0.5


def analytical_posterior_c_given_a(a_val: float) -> tuple[float, float]:
    """P(C | A=a) for the linear Gaussian model.

    B | A=a ~ N(2a, 1)
    C = 0.5*B + eps, eps ~ N(0,0.5)
    => C | A=a ~ N(0.5*2a, sqrt(0.5^2*1^2 + 0.5^2)) = N(a, sqrt(0.5))
    """
    mean = a_val  # 0.5 * 2 * a
    std = np.sqrt(0.5**2 * 1.0**2 + 0.5**2)  # sqrt(0.25 + 0.25) = sqrt(0.5)
    return mean, std


def analytical_interventional_c_do_a(a_val: float) -> tuple[float, float]:
    """P(C | do(A=a)) for the linear Gaussian model.

    do(A=a): A is fixed at a (same as conditioning for this linear model).
    B = 2*a + N(0,1), C = 0.5*B + N(0,0.5)
    => C | do(A=a) ~ N(a, sqrt(0.5))
    """
    return analytical_posterior_c_given_a(a_val)


# ------------------------------------------------------------------
# Evaluation functions
# ------------------------------------------------------------------


def print_section(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def eval_posterior_vs_analytical(n_trials: int = 30):
    """Compare SCMSolver posteriors against closed-form Gaussian posteriors.

    For each trial: sample a true A, compute P(B|A) and P(C|A) analytically,
    compare full distribution (KS test) + mean + std.
    """
    world = make_linear_gaussian()
    solver = SCMSolver(world)

    results = {"B|A": [], "C|A": [], "C|B": []}

    for trial in range(n_trials):
        state = solver.sample_state(seed=trial * 37)

        # P(B | A=a_true)
        a_val = state["A"]
        post_b = solver.posterior_samples("B", evidence={"A": a_val}, n=5000, seed=trial)
        true_mean_b, true_std_b = analytical_posterior_b_given_a(a_val)
        ks_stat_b, ks_p_b = stats.kstest(
            post_b, "norm", args=(true_mean_b, true_std_b)
        )
        results["B|A"].append({
            "a_val": a_val,
            "mc_mean": np.mean(post_b),
            "true_mean": true_mean_b,
            "mean_err": abs(np.mean(post_b) - true_mean_b),
            "mc_std": np.std(post_b),
            "true_std": true_std_b,
            "std_err": abs(np.std(post_b) - true_std_b),
            "ks_stat": ks_stat_b,
            "ks_p": ks_p_b,
            "n_samples": len(post_b),
        })

        # P(C | A=a_true) — this goes through B, tests indirect conditioning
        post_c_a = solver.posterior_samples("C", evidence={"A": a_val}, n=5000, seed=trial)
        true_mean_c, true_std_c = analytical_posterior_c_given_a(a_val)
        ks_stat_c, ks_p_c = stats.kstest(
            post_c_a, "norm", args=(true_mean_c, true_std_c)
        )
        results["C|A"].append({
            "a_val": a_val,
            "mc_mean": np.mean(post_c_a),
            "true_mean": true_mean_c,
            "mean_err": abs(np.mean(post_c_a) - true_mean_c),
            "mc_std": np.std(post_c_a),
            "true_std": true_std_c,
            "std_err": abs(np.std(post_c_a) - true_std_c),
            "ks_stat": ks_stat_c,
            "ks_p": ks_p_c,
            "n_samples": len(post_c_a),
        })

        # P(C | B=b_true) — direct parent
        b_val = state["B"]
        post_c_b = solver.posterior_samples("C", evidence={"B": b_val}, n=5000, seed=trial)
        true_mean_cb, true_std_cb = analytical_posterior_c_given_b(b_val)
        ks_stat_cb, ks_p_cb = stats.kstest(
            post_c_b, "norm", args=(true_mean_cb, true_std_cb)
        )
        results["C|B"].append({
            "b_val": b_val,
            "mc_mean": np.mean(post_c_b),
            "true_mean": true_mean_cb,
            "mean_err": abs(np.mean(post_c_b) - true_mean_cb),
            "mc_std": np.std(post_c_b),
            "true_std": true_std_cb,
            "std_err": abs(np.std(post_c_b) - true_std_cb),
            "ks_stat": ks_stat_cb,
            "ks_p": ks_p_cb,
            "n_samples": len(post_c_b),
        })

    # Print results
    for cond, trials in results.items():
        mean_errs = [t["mean_err"] for t in trials]
        std_errs = [t["std_err"] for t in trials]
        ks_stats = [t["ks_stat"] for t in trials]
        ks_ps = [t["ks_p"] for t in trials]
        n_samples = [t["n_samples"] for t in trials]
        ks_pass = sum(1 for p in ks_ps if p > 0.05)

        print(f"  {cond}:")
        print(f"    Mean error:  {np.mean(mean_errs):.4f} +/- {np.std(mean_errs):.4f}")
        print(f"    Std error:   {np.mean(std_errs):.4f} +/- {np.std(std_errs):.4f}")
        print(f"    KS statistic: {np.mean(ks_stats):.4f} +/- {np.std(ks_stats):.4f}")
        print(f"    KS pass rate (p>0.05): {ks_pass}/{n_trials} "
              f"({100*ks_pass/n_trials:.0f}%)")
        print(f"    Avg samples accepted: {np.mean(n_samples):.0f}")
        print()

    return results


def eval_interventional_with_evidence():
    """Test P(C | do(A=a), B=b) — forces rejection sampling path.

    Analytical: do(A=a) fixes A. B = 2*a + N(0,1).
    P(C | do(A=a), B=b) = P(C | B=b) = N(0.5*b, 0.5).
    """
    world = make_linear_gaussian()
    solver = SCMSolver(world)

    print("  Testing P(C | do(A=a), B=b) against analytical N(0.5*b, 0.5)")
    print()

    results = []
    for trial in range(20):
        a_val = 5.0 + trial * 0.5  # vary intervention level
        # B|do(A=a) ~ N(2a, 1) — sample a plausible b
        rng = np.random.default_rng(trial)
        b_val = 2 * a_val + rng.normal(0, 1)

        post = solver.interventional_samples(
            "C", do={"A": a_val}, evidence={"B": b_val},
            n=5000, seed=trial,
        )

        true_mean, true_std = 0.5 * b_val, 0.5
        mc_mean = np.mean(post)
        mc_std = np.std(post)

        ks_stat, ks_p = stats.kstest(post, "norm", args=(true_mean, true_std))

        results.append({
            "a": a_val, "b": b_val,
            "mc_mean": mc_mean, "true_mean": true_mean,
            "mean_err": abs(mc_mean - true_mean),
            "mc_std": mc_std, "true_std": true_std,
            "std_err": abs(mc_std - true_std),
            "ks_stat": ks_stat, "ks_p": ks_p,
            "n_samples": len(post),
        })

    mean_errs = [r["mean_err"] for r in results]
    std_errs = [r["std_err"] for r in results]
    ks_pass = sum(1 for r in results if r["ks_p"] > 0.05)
    n_samples = [r["n_samples"] for r in results]

    print(f"    Mean error:  {np.mean(mean_errs):.4f} +/- {np.std(mean_errs):.4f}")
    print(f"    Std error:   {np.mean(std_errs):.4f} +/- {np.std(std_errs):.4f}")
    print(f"    KS pass rate (p>0.05): {ks_pass}/{len(results)} "
          f"({100*ks_pass/len(results):.0f}%)")
    print(f"    Avg samples: {np.mean(n_samples):.0f}")
    print()

    return results


def eval_ig_stability(n_seeds: int = 5):
    """Run IG ranking with multiple seeds, report mean +/- std.

    Tests whether the RANKING is stable, not just the values.
    """
    worlds = {
        "chain_5": (make_chain(5), "X4", ["X0", "X1", "X2", "X3"]),
        "diamond": (make_diamond(), "D", ["A", "B", "C"]),
        "fork_5": (make_fork(5), "C4", ["Z", "C0", "C1", "C2", "C3"]),
    }

    results = {}
    for name, (world, target, candidates) in worlds.items():
        solver = SCMSolver(world)

        # Collect IG values across seeds
        ig_by_seed = {c: [] for c in candidates}
        rankings = []

        for seed in range(n_seeds):
            igs = {}
            for c in candidates:
                ig = solver.information_gain(
                    target, evidence={}, candidate=c,
                    n=50_000, seed=seed * 1000 + 42,
                )
                igs[c] = ig
                ig_by_seed[c].append(ig)

            ranking = sorted(igs.keys(), key=lambda v: -igs[v])
            rankings.append(ranking)

        # Compute stability
        first_choices = [r[0] for r in rankings]
        most_common_first = max(set(first_choices), key=first_choices.count)
        first_agreement = first_choices.count(most_common_first) / n_seeds

        # Check if full ranking is identical across all seeds
        ranking_stable = all(r == rankings[0] for r in rankings)

        print(f"  {name} (target={target}):")
        for c in candidates:
            vals = ig_by_seed[c]
            print(f"    IG({c:>3s}) = {np.mean(vals):.4f} +/- {np.std(vals):.4f}  "
                  f"[{min(vals):.4f}, {max(vals):.4f}]")
        print(f"    First choice agreement: {first_agreement:.0%} ({most_common_first})")
        print(f"    Full ranking stable: {ranking_stable}")
        if not ranking_stable:
            print(f"    Rankings: {rankings}")
        print()

        results[name] = {
            "ig_by_seed": ig_by_seed,
            "rankings": rankings,
            "first_agreement": first_agreement,
            "ranking_stable": ranking_stable,
        }

    return results


def eval_acceptance_rates():
    """Report rejection sampling acceptance rates for various evidence scenarios."""
    world = make_linear_gaussian()
    solver = SCMSolver(world)

    print("  Evidence scenario             | Accepted | Rate    | Tolerance widens")
    print("  " + "-" * 70)

    scenarios = [
        ("A=mean (10)", {"A": 10.0}),
        ("A=+1std (12)", {"A": 12.0}),
        ("A=+2std (14)", {"A": 14.0}),
        ("A=+3std (16)", {"A": 16.0}),
        ("A=10, B=20", {"A": 10.0, "B": 20.0}),
        ("A=10, B=20, C=10", {"A": 10.0, "B": 20.0, "C": 10.0}),
    ]

    results = []
    for label, evidence in scenarios:
        n_total = 100_000
        df = world.sample(n=n_total, seed=42)

        # Track acceptance at each tolerance level
        accepted_per_level = []
        for attempt in range(6):
            factor = 1.5 ** attempt
            import pandas as pd
            mask = pd.Series(True, index=df.index)
            for var, val in evidence.items():
                col_std = df[var].std()
                tol = max(col_std * 0.1 * factor, 1e-6)
                mask &= (np.abs(df[var] - val) < tol)
            accepted_per_level.append(int(mask.sum()))

        # Find first level with >= 100 matches
        first_ok = next(
            (i for i, n in enumerate(accepted_per_level) if n >= 100), -1
        )

        final_accepted = solver._rejection_filter(df, evidence)
        n_accepted = len(final_accepted)
        rate = n_accepted / n_total

        results.append({
            "label": label,
            "n_accepted": n_accepted,
            "rate": rate,
            "widens": first_ok,
            "per_level": accepted_per_level,
        })

        print(f"  {label:30s} | {n_accepted:8d} | {rate:6.3%} | "
              f"{'none' if first_ok == 0 else f'{first_ok}x' if first_ok > 0 else 'FAIL'}")

    print()
    print("  Acceptance per tolerance level (1x, 1.5x, 2.25x, ...):")
    for r in results:
        levels_str = " -> ".join(str(n) for n in r["per_level"])
        print(f"    {r['label']:30s}: {levels_str}")

    return results


def eval_scale(sizes: list[int]):
    """Measure timing and IG correctness as graph size grows."""
    results = []
    for n in sizes:
        world = make_chain(n)
        solver = SCMSolver(world)
        target = f"X{n-1}"
        parent = f"X{n-2}"
        distant = "X0"

        t0 = time.perf_counter()
        ig_parent = solver.information_gain(
            target, evidence={}, candidate=parent, n=50_000, seed=42
        )
        t_ig = time.perf_counter() - t0

        ig_distant = solver.information_gain(
            target, evidence={}, candidate=distant, n=50_000, seed=42
        )

        available = [f"X{i}" for i in range(n - 1)]
        t0 = time.perf_counter()
        _, traj = solver.generate_trajectory(target, available, budget=3, seed=42)
        t_traj = time.perf_counter() - t0

        obs_nodes = [t.recommended_action.node for t in traj if t.recommended_action]

        results.append({
            "n": n,
            "ig_parent": ig_parent,
            "ig_distant": ig_distant,
            "parent_wins": ig_parent > ig_distant,
            "t_ig": t_ig,
            "t_traj": t_traj,
            "first_obs": obs_nodes[:3],
        })

    print(f"  {'N':>3s} | {'IG(parent)':>10s} | {'IG(distant)':>11s} | "
          f"{'Win':>3s} | {'t_IG':>6s} | {'t_traj':>7s} | First obs")
    print(f"  {'-'*3}-+-{'-'*10}-+-{'-'*11}-+-"
          f"{'-'*3}-+-{'-'*6}-+-{'-'*7}-+---------")
    for r in results:
        print(f"  {r['n']:3d} | {r['ig_parent']:10.4f} | {r['ig_distant']:11.4f} | "
              f"{'Y' if r['parent_wins'] else 'N':>3s} | "
              f"{r['t_ig']:6.2f} | {r['t_traj']:7.2f} | {r['first_obs']}")

    return results


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------


def main():
    print("SCMSolver Rigorous Evaluation")
    print("=" * 70)

    # 1. Posterior vs analytical
    print_section("1. POSTERIOR vs ANALYTICAL (Linear Gaussian)")
    print("  Gold standard: comparing MC posteriors against closed-form N(mu, sigma)")
    print("  KS test: p>0.05 means distributions are statistically indistinguishable")
    print()
    post_results = eval_posterior_vs_analytical(n_trials=30)

    # 2. Interventional with evidence
    print_section("2. INTERVENTIONAL with EVIDENCE (rejection sampling path)")
    interv_results = eval_interventional_with_evidence()

    # 3. IG stability across seeds
    print_section("3. IG RANKING STABILITY (5 seeds)")
    ig_results = eval_ig_stability(n_seeds=5)

    # 4. Acceptance rates
    print_section("4. REJECTION SAMPLING ACCEPTANCE RATES")
    acc_results = eval_acceptance_rates()

    # 5. Scale
    print_section("5. SCALE BEHAVIOR")
    scale_results = eval_scale([5, 8, 10, 15])

    # Summary
    print_section("SUMMARY")

    # Posterior quality
    all_ks_pass = []
    for cond, trials in post_results.items():
        ks_pass_rate = sum(1 for t in trials if t["ks_p"] > 0.05) / len(trials)
        all_ks_pass.append(ks_pass_rate)
        verdict = "GOOD" if ks_pass_rate > 0.7 else "WARN" if ks_pass_rate > 0.4 else "FAIL"
        print(f"  Posterior {cond}: KS pass {ks_pass_rate:.0%} [{verdict}]")

    # IG stability
    all_stable = all(r["ranking_stable"] for r in ig_results.values())
    all_first_agree = all(r["first_agreement"] >= 0.8 for r in ig_results.values())
    print(f"  IG ranking stable: {all_stable}")
    print(f"  IG first choice >= 80% agreement: {all_first_agree}")

    # Scale
    all_parent_wins = all(r["parent_wins"] for r in scale_results)
    print(f"  Parent always wins: {all_parent_wins}")
    print(f"  Max trajectory time: {scale_results[-1]['t_traj']:.1f}s")

    # Overall verdict
    overall_ok = (
        min(all_ks_pass) > 0.4
        and all_first_agree
        and all_parent_wins
    )
    print()
    if overall_ok:
        print("  VERDICT: SCMSolver passes rigorous evaluation.")
    else:
        print("  VERDICT: SCMSolver has issues. Review details above.")


if __name__ == "__main__":
    main()
