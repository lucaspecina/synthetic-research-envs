"""Tests for salience map generator."""

from __future__ import annotations

from sreg.tools.oi_salience import build_salience_map
from sreg.world.scm import SCMWorld


def _research_world() -> SCMWorld:
    """A 6-variable research world with known causal structure.

    C -> A -> M -> Y
    C -> Y
    Z -> Y (interaction with A)
    X (independent noise)

    Known truths:
    - A causes Y (strong, via M and direct)
    - C confounds A->Y
    - M mediates A->Y
    - Z modifies the effect of A on Y
    - X has no effect on Y
    """
    return SCMWorld(
        id="test-research",
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
                0.5 * p["A"] + 0.4 * p["M"] + 0.3 * p["C"]
                + 0.3 * p["A"] * p["Z"]  # interaction
                + rng.normal(0, 0.3)
            ),
        },
    )


class TestBuildSalienceMap:
    def test_basic_map_generation(self):
        """Map should be generated without errors."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=10_000, seed=42)
        assert smap.world_id == "test-research"
        assert smap.brief_target == "Y"
        assert len(smap.families) > 0

    def test_map_finds_main_effects(self):
        """Should find A->Y and C->Y as significant causal effects."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=20_000, seed=42)

        focus_sigs = [f.key.focus_signature for f in smap.families]
        # A->Y should be found
        assert any("A" in sig and "Y" in sig for sig in focus_sigs), (
            f"Expected A->Y effect, found: {focus_sigs}"
        )

    def test_map_respects_cap(self):
        """Map should not exceed max families."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=10_000, seed=42, max_families=5)
        assert len(smap.families) <= 5

    def test_independent_variable_excluded(self):
        """X (independent) should not appear as a significant effect on Y."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=20_000, seed=42)

        # X is not an ancestor of Y, so it shouldn't appear in any family
        for f in smap.families:
            focus = set(f.key.focus_signature) - {"Y"}
            assert "X" not in focus, f"X should not be in family: {f.key}"

    def test_families_have_valid_specs(self):
        """Each family should have valid AtomicSpecs."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=10_000, seed=42)

        for family in smap.families:
            assert len(family.atoms) >= 1
            for atom in family.atoms:
                assert atom.spec.spec_id
                assert len(atom.spec.arms) >= 1
                assert atom.weight > 0

    def test_pattern_diversity(self):
        """Map should have diverse pattern classes, not just causal_effect."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=20_000, seed=42)

        patterns = {f.key.pattern_class for f in smap.families}
        # Should have at least 2 different pattern types
        assert len(patterns) >= 2, f"Expected diverse patterns, got: {patterns}"

    def test_salience_ordering(self):
        """Families should be ordered by salience (descending)."""
        world = _research_world()
        smap = build_salience_map(world, target="Y", n_mc=10_000, seed=42)

        saliences = [f.salience for f in smap.families]
        assert saliences == sorted(saliences, reverse=True)


class TestMinimalWorld:
    def test_two_node_world(self):
        """Simplest possible: A -> Y."""
        world = SCMWorld(
            id="test-minimal",
            graph={"A": [], "Y": ["A"]},
            equations={
                "A": lambda p, rng: rng.normal(0, 1),
                "Y": lambda p, rng: 0.8 * p["A"] + rng.normal(0, 0.5),
            },
        )
        smap = build_salience_map(world, target="Y", n_mc=10_000, seed=42)
        assert len(smap.families) >= 1
        # Should find A->Y
        assert any("A" in f.key.focus_signature for f in smap.families)

    def test_no_ancestors_empty_map(self):
        """Root target with no ancestors should produce empty map."""
        world = SCMWorld(
            id="test-root",
            graph={"Y": [], "Z": ["Y"]},
            equations={
                "Y": lambda p, rng: rng.normal(0, 1),
                "Z": lambda p, rng: p["Y"] + rng.normal(0, 0.5),
            },
        )
        smap = build_salience_map(world, target="Y", n_mc=10_000, seed=42)
        assert len(smap.families) == 0
