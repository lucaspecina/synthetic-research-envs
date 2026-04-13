"""Tests for OI Compiler: WorldSummary and shared types."""

from __future__ import annotations

from sreg.tools.oi_compiler import build_world_summary
from sreg.world.scm import SCMWorld

# ---------------------------------------------------------------------------
# Test world
# ---------------------------------------------------------------------------


def _test_world() -> SCMWorld:
    """C -> A -> M -> Y, C -> Y, Z -> Y: diverse causal structure."""
    return SCMWorld(
        id="compiler-test",
        graph={
            "C": [],
            "A": ["C"],
            "M": ["A"],
            "Z": [],
            "Y": ["A", "M", "C", "Z"],
        },
        equations={
            "C": lambda p, rng: rng.normal(0, 1),
            "A": lambda p, rng: 0.8 * p["C"] + rng.normal(0, 0.5),
            "M": lambda p, rng: 0.6 * p["A"] + rng.normal(0, 0.3),
            "Z": lambda p, rng: rng.normal(0, 1),
            "Y": lambda p, rng: (
                0.5 * p["A"]
                + 0.4 * p["M"]
                + 0.3 * p["C"]
                + 0.2 * p["Z"]
                + rng.normal(0, 0.3)
            ),
        },
    )


# ---------------------------------------------------------------------------
# WorldSummary tests
# ---------------------------------------------------------------------------


class TestWorldSummary:
    def test_build_summary(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        assert summary.world_id == "compiler-test"
        assert summary.target == "Y"
        assert len(summary.variables) == 5
        assert "A" in summary.observable_names

    def test_anchors(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        a = summary.anchors("A")
        assert a.p25 < a.p50 < a.p75
        assert a.std > 0

    def test_hi_lo(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        assert summary.hi("A") > summary.lo("A")
        assert summary.mid("A") > summary.lo("A")
        assert summary.mid("A") < summary.hi("A")

    def test_missing_variable_raises(self):
        world = _test_world()
        summary = build_world_summary(world, "Y", n_mc=10_000, seed=42)

        import pytest

        with pytest.raises(ValueError, match="not in world summary"):
            summary.anchors("NONEXISTENT")

