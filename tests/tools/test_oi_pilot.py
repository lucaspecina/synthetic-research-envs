"""Pilot E2E test: validate that OI scoring separates oracle, no-data, and shotgun.

This is the critical validation: if the scoring can't separate a solver that
knows the truth from one that guesses, the pipeline is broken regardless
of how good the compiler is.

Three simulated "solvers":
- Oracle: knows the truth, submits correct claims matching salience families
- No-data: guesses claims without investigating (random directions)
- Shotgun: submits many claims hoping some stick (max K, random)
"""

from __future__ import annotations

import numpy as np

from sreg.solver.scm_solver import SCMSolver
from sreg.tools.oi_salience import build_salience_map
from sreg.tools.oi_verifier import score_claim_against_family, score_episode, verify_atom
from sreg.world.scm import SCMWorld


def _research_world() -> SCMWorld:
    """6-variable world with known structure for pilot testing."""
    return SCMWorld(
        id="pilot-world",
        graph={
            "C": [],
            "A": ["C"],
            "M": ["A"],
            "Z": [],
            "X": [],
            "Y": ["A", "M", "C", "Z"],
        },
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 0.8 * p["C"] + rng.normal(0, 0.5),
            "M": lambda p, rng: 0.6 * p["A"] + rng.normal(0, 0.3),
            "Z": lambda p, rng: rng.normal(0, 1),
            "X": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: (
                0.5 * p["A"]
                + 0.4 * p["M"]
                + 0.3 * p["C"]
                + 0.3 * p["A"] * p["Z"]
                + rng.normal(0, 0.3)
            ),
        },
    )


def _oracle_claims(world: SCMWorld, solver: SCMSolver, smap) -> list[tuple[str, float]]:
    """Oracle solver: submits claims that perfectly match family atoms."""
    matches = []
    for family in smap.families[:3]:  # Take top 3 families
        atom_scores = {}
        for atom in family.atoms:
            verdict = verify_atom(atom.spec, world, solver, n_mc=20_000, seed=42)
            atom_scores[atom.atom_id] = verdict.score
        score, _ = score_claim_against_family(atom_scores, family)
        matches.append((family.family_id, score))
    return matches


def _nodata_claims(world: SCMWorld, smap) -> list[tuple[str, float]]:
    """No-data solver: guesses random directions for family atoms."""
    rng = np.random.default_rng(123)
    matches = []
    for family in smap.families[:3]:
        # Randomly assign scores (50/50 right/wrong)
        atom_scores = {}
        for atom in family.atoms:
            atom_scores[atom.atom_id] = float(rng.choice([0.0, 1.0]))
        score, _ = score_claim_against_family(atom_scores, family)
        matches.append((family.family_id, score))
    return matches


def _shotgun_claims(world: SCMWorld, solver: SCMSolver, smap) -> list[tuple[str, float]]:
    """Shotgun solver: submits max claims, half wrong."""
    rng = np.random.default_rng(456)
    matches = []
    all_families = smap.families
    for family in all_families[:5]:  # Max K=5
        atom_scores = {}
        for atom in family.atoms:
            # 40% chance of getting it right (shotgun)
            atom_scores[atom.atom_id] = float(rng.random() > 0.6)
        score, _ = score_claim_against_family(atom_scores, family)
        matches.append((family.family_id, score))
    return matches


class TestPilotE2E:
    """Validate that scoring separates oracle, no-data, and shotgun."""

    def test_oracle_beats_nodata(self):
        """Oracle (knows truth) should clearly beat no-data (guesses)."""
        world = _research_world()
        solver = SCMSolver(world)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        oracle_matches = _oracle_claims(world, solver, smap)
        nodata_matches = _nodata_claims(world, smap)

        oracle_ep = score_episode(oracle_matches, smap.families, n_claims=3)
        nodata_ep = score_episode(nodata_matches, smap.families, n_claims=3)

        print(
            f"\nOracle:  correctness={oracle_ep.correctness:.3f} "
            f"coverage={oracle_ep.coverage:.3f} total={oracle_ep.total:.3f}"
        )
        print(
            f"No-data: correctness={nodata_ep.correctness:.3f} "
            f"coverage={nodata_ep.coverage:.3f} total={nodata_ep.total:.3f}"
        )

        assert oracle_ep.total > nodata_ep.total, (
            f"Oracle ({oracle_ep.total:.3f}) should beat no-data ({nodata_ep.total:.3f})"
        )
        # The margin should be interpretable (>0.1)
        assert oracle_ep.total - nodata_ep.total > 0.10, (
            f"Margin too small: {oracle_ep.total - nodata_ep.total:.3f}"
        )

    def test_oracle_beats_shotgun(self):
        """Oracle should beat shotgun (many guesses, some right)."""
        world = _research_world()
        solver = SCMSolver(world)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        oracle_matches = _oracle_claims(world, solver, smap)
        shotgun_matches = _shotgun_claims(world, solver, smap)

        oracle_ep = score_episode(oracle_matches, smap.families, n_claims=3)
        shotgun_ep = score_episode(shotgun_matches, smap.families, n_claims=5)

        print(
            f"\nOracle:  correctness={oracle_ep.correctness:.3f} "
            f"coverage={oracle_ep.coverage:.3f} total={oracle_ep.total:.3f}"
        )
        print(
            f"Shotgun: correctness={shotgun_ep.correctness:.3f} "
            f"coverage={shotgun_ep.coverage:.3f} total={shotgun_ep.total:.3f}"
        )

        assert oracle_ep.total > shotgun_ep.total, (
            f"Oracle ({oracle_ep.total:.3f}) should beat shotgun ({shotgun_ep.total:.3f})"
        )

    def test_precision_gate_blocks_shotgun_coverage(self):
        """Shotgun with low precision should get zero coverage."""
        world = _research_world()
        smap = build_salience_map(world, "Y", n_mc=10_000, seed=42)

        # Simulate very bad shotgun: all wrong
        bad_matches = [(f.family_id, 0.1) for f in smap.families[:5]]
        ep = score_episode(bad_matches, smap.families, n_claims=5)

        assert ep.precision_gate_active is True
        assert ep.coverage == 0.0

    def test_score_summary(self):
        """Print full summary for manual inspection."""
        world = _research_world()
        solver = SCMSolver(world)
        smap = build_salience_map(world, "Y", n_mc=20_000, seed=42)

        oracle_matches = _oracle_claims(world, solver, smap)
        nodata_matches = _nodata_claims(world, smap)
        shotgun_matches = _shotgun_claims(world, solver, smap)

        oracle_ep = score_episode(oracle_matches, smap.families, n_claims=3)
        nodata_ep = score_episode(nodata_matches, smap.families, n_claims=3)
        shotgun_ep = score_episode(shotgun_matches, smap.families, n_claims=5)

        print("\n=== PILOT E2E RESULTS ===")
        print(f"World: {world.id} ({len(world.variables)} vars, target=Y)")
        print(f"Salience map: {len(smap.families)} families")
        print(f"\n{'Solver':<12} {'Correct':>8} {'Coverage':>8} {'Effic':>8} {'TOTAL':>8}")
        print("-" * 50)
        print(
            f"{'Oracle':<12} {oracle_ep.correctness:>8.3f} {oracle_ep.coverage:>8.3f} "
            f"{oracle_ep.efficiency:>8.3f} {oracle_ep.total:>8.3f}"
        )
        print(
            f"{'No-data':<12} {nodata_ep.correctness:>8.3f} {nodata_ep.coverage:>8.3f} "
            f"{nodata_ep.efficiency:>8.3f} {nodata_ep.total:>8.3f}"
        )
        print(
            f"{'Shotgun':<12} {shotgun_ep.correctness:>8.3f} {shotgun_ep.coverage:>8.3f} "
            f"{shotgun_ep.efficiency:>8.3f} {shotgun_ep.total:>8.3f}"
        )
        print("=" * 50)

        # Verify ordering: oracle > shotgun > no-data (or oracle > no-data > shotgun)
        assert oracle_ep.total > max(nodata_ep.total, shotgun_ep.total)
