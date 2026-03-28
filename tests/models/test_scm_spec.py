"""Tests for SCMSpec Pydantic model validation."""

import pytest

from sreg.models.scm_spec import SCMSpec, SCMVariableSpec


def _var(name: str, role: str = "observable", equation: str = "normal(0, 1)"):
    """Shortcut to create a variable spec."""
    return SCMVariableSpec(name=name, role=role, equation=equation)


class TestValidSpec:
    def test_minimal_valid(self):
        spec = SCMSpec(
            variables=[
                _var("X", role="observable"),
                _var("Y", role="target", equation="0.5 * X + normal(0, 1)"),
            ],
            edges=[("X", "Y")],
        )
        assert len(spec.variables) == 2
        assert len(spec.edges) == 1

    def test_no_edges_valid(self):
        """All roots, no edges -- trivially acyclic."""
        spec = SCMSpec(
            variables=[
                _var("A", role="observable"),
                _var("B", role="target"),
            ],
            edges=[],
        )
        assert len(spec.edges) == 0

    def test_complex_graph(self):
        spec = SCMSpec(
            variables=[
                _var("A"),
                _var("B"),
                _var("C", role="latent"),
                _var("D", role="target"),
            ],
            edges=[("A", "C"), ("B", "C"), ("C", "D"), ("A", "D")],
        )
        assert len(spec.variables) == 4

    def test_with_metadata(self):
        spec = SCMSpec(
            variables=[
                SCMVariableSpec(
                    name="temperature",
                    role="observable",
                    unit="celsius",
                    range=(15.0, 40.0),
                    description="Ambient temperature",
                    equation="normal(25, 5)",
                ),
                SCMVariableSpec(
                    name="growth",
                    role="target",
                    unit="mm/day",
                    range=(0.0, 10.0),
                    description="Plant growth rate",
                    equation="0.5 * temperature + normal(0, 1)",
                ),
            ],
            edges=[("temperature", "growth")],
        )
        assert spec.variables[0].unit == "celsius"
        assert spec.variables[0].range == (15.0, 40.0)


class TestValidation:
    def test_duplicate_names_rejected(self):
        with pytest.raises(ValueError, match="Duplicate"):
            SCMSpec(
                variables=[_var("X"), _var("X", role="target")],
                edges=[],
            )

    def test_unknown_edge_source_rejected(self):
        with pytest.raises(ValueError, match="unknown variable 'Z'"):
            SCMSpec(
                variables=[_var("X"), _var("Y", role="target")],
                edges=[("Z", "Y")],
            )

    def test_unknown_edge_target_rejected(self):
        with pytest.raises(ValueError, match="unknown variable 'Z'"):
            SCMSpec(
                variables=[_var("X"), _var("Y", role="target")],
                edges=[("X", "Z")],
            )

    def test_cycle_rejected(self):
        with pytest.raises(ValueError, match="cycles"):
            SCMSpec(
                variables=[_var("X"), _var("Y", role="target")],
                edges=[("X", "Y"), ("Y", "X")],
            )

    def test_no_target_accepted(self):
        """target role is no longer required — OI uses sub-question roles."""
        spec = SCMSpec(
            variables=[_var("X"), _var("Y")],
            edges=[("X", "Y")],
        )
        assert len(spec.variables) == 2

    def test_no_observable_rejected(self):
        with pytest.raises(ValueError, match="observable"):
            SCMSpec(
                variables=[
                    _var("X", role="latent"),
                    _var("Y", role="latent"),
                ],
                edges=[("X", "Y")],
            )

    def test_legacy_target_as_observable(self):
        """Legacy 'target' role accepted and treated as non-latent."""
        spec = SCMSpec(
            variables=[
                _var("X", role="latent"),
                _var("Y", role="target"),
            ],
            edges=[("X", "Y")],
        )
        assert spec.variables[1].role == "target"  # preserved in model

    def test_too_few_variables(self):
        with pytest.raises(ValueError):
            SCMSpec(
                variables=[_var("X", role="target")],
                edges=[],
            )

    def test_reserved_name_rejected(self):
        """Variable named 'normal' would shadow the distribution function."""
        with pytest.raises(ValueError, match="conflicts with a built-in"):
            _var("normal")

    def test_keyword_name_rejected(self):
        """Python keywords are not valid variable names."""
        with pytest.raises(ValueError, match="keyword"):
            _var("for")

    def test_invalid_identifier_rejected(self):
        """Names with hyphens or spaces are not valid identifiers."""
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            _var("foo-bar")

    def test_other_reserved_names(self):
        for name in ("exp", "log", "sqrt", "abs", "min", "max", "uniform"):
            with pytest.raises(ValueError, match="conflicts"):
                _var(name)

    def test_duplicate_edges_rejected(self):
        with pytest.raises(ValueError, match="Duplicate edge"):
            SCMSpec(
                variables=[_var("A"), _var("B", role="target")],
                edges=[("A", "B"), ("A", "B")],
            )


class TestReservedNamesSync:
    def test_reserved_names_match_compiler(self):
        """Ensure _RESERVED_NAMES in scm_spec matches _ALLOWED_FUNCTIONS in compiler."""
        from sreg.models.scm_spec import _RESERVED_NAMES
        from sreg.world.expression_compiler import _ALLOWED_FUNCTIONS

        assert _RESERVED_NAMES == _ALLOWED_FUNCTIONS, (
            f"Drift detected! "
            f"Only in spec: {_RESERVED_NAMES - _ALLOWED_FUNCTIONS}, "
            f"Only in compiler: {_ALLOWED_FUNCTIONS - _RESERVED_NAMES}"
        )


class TestConvenience:
    def test_variable_names(self):
        spec = SCMSpec(
            variables=[_var("A"), _var("B", role="target")],
            edges=[("A", "B")],
        )
        assert spec.variable_names() == ["A", "B"]

    def test_get_variable(self):
        spec = SCMSpec(
            variables=[_var("A"), _var("B", role="target")],
            edges=[],
        )
        v = spec.get_variable("B")
        assert v.name == "B"
        assert v.role == "target"

    def test_get_variable_missing(self):
        spec = SCMSpec(
            variables=[_var("A"), _var("B", role="target")],
            edges=[],
        )
        with pytest.raises(KeyError, match="'C'"):
            spec.get_variable("C")

    def test_parents_of(self):
        spec = SCMSpec(
            variables=[_var("A"), _var("B"), _var("C", role="target")],
            edges=[("A", "C"), ("B", "C")],
        )
        assert sorted(spec.parents_of("C")) == ["A", "B"]
        assert spec.parents_of("A") == []
