"""Tests for SCMWorldGenTool: generation, validation, and integration."""

import numpy as np
import pytest

from sreg.models.scm_spec import SCMSpec, SCMVariableSpec
from sreg.tools.scm_world_gen import SCMWorldGenTool
from sreg.world.expression_compiler import ExpressionError
from sreg.world.scm import SCMWorld


def _var(
    name: str,
    role: str = "observable",
    equation: str = "normal(0, 1)",
    unit: str = "",
    range: tuple[float, float] | None = None,
    description: str = "",
):
    return SCMVariableSpec(
        name=name,
        role=role,
        equation=equation,
        unit=unit,
        range=range,
        description=description,
    )


@pytest.fixture
def tool():
    return SCMWorldGenTool()


# ------------------------------------------------------------------
# Basic generation
# ------------------------------------------------------------------


class TestGenerate:
    def test_linear_chain(self, tool):
        """A -> B -> C with linear equations."""
        spec = SCMSpec(
            variables=[
                _var("A", equation="normal(10, 2)"),
                _var("B", equation="0.5 * A + normal(0, 1)"),
                _var("C", role="target", equation="0.3 * B + normal(0, 0.5)"),
            ],
            edges=[("A", "B"), ("B", "C")],
        )
        world = tool.generate(spec)

        assert isinstance(world, SCMWorld)
        assert set(world.variables) == {"A", "B", "C"}
        assert world.id.startswith("scm-")

    def test_nonlinear_equations(self, tool):
        """Sigmoid, threshold, power relationships."""
        spec = SCMSpec(
            variables=[
                _var("dose", equation="uniform(0, 100)", unit="mg"),
                _var(
                    "response",
                    role="target",
                    equation="100 / (1 + exp(-0.1 * (dose - 50))) + normal(0, 5)",
                    unit="percent",
                ),
            ],
            edges=[("dose", "response")],
        )
        world = tool.generate(spec)
        df = world.sample(100, seed=0)

        assert df["dose"].min() >= 0
        assert df["dose"].max() <= 100

    def test_multiple_parents(self, tool):
        """Node with multiple parents and interaction."""
        spec = SCMSpec(
            variables=[
                _var("temperature", equation="normal(25, 5)", unit="celsius"),
                _var("humidity", equation="normal(60, 10)", unit="percent"),
                _var(
                    "growth",
                    role="target",
                    equation=(
                        "0.5 * temperature + 0.2 * humidity "
                        "+ 0.01 * temperature * humidity + normal(0, 2)"
                    ),
                    unit="mm/day",
                ),
            ],
            edges=[("temperature", "growth"), ("humidity", "growth")],
        )
        world = tool.generate(spec)
        assert world.parents("growth") == ["temperature", "humidity"]

    def test_latent_variable(self, tool):
        """Latent variable properly marked."""
        spec = SCMSpec(
            variables=[
                _var("L", role="latent", equation="normal(0, 1)"),
                _var("X", equation="0.5 * L + normal(0, 0.5)"),
                _var("Y", role="target", equation="0.3 * L + normal(0, 0.5)"),
            ],
            edges=[("L", "X"), ("L", "Y")],
        )
        world = tool.generate(spec)

        assert "L" in world.latent_variables
        assert "X" not in world.latent_variables
        assert "L" not in world.observable_variables
        assert "X" in world.observable_variables

    def test_metadata_preserved(self, tool):
        """Variable metadata carried to SCMWorld."""
        spec = SCMSpec(
            variables=[
                _var(
                    "temp",
                    equation="normal(25, 5)",
                    unit="celsius",
                    range=(15.0, 40.0),
                    description="Ambient temperature",
                ),
                _var("growth", role="target", equation="0.5 * temp + normal(0, 1)"),
            ],
            edges=[("temp", "growth")],
        )
        world = tool.generate(spec)

        meta = world.variable_meta["temp"]
        assert meta.unit == "celsius"
        assert meta.range == (15.0, 40.0)
        assert meta.description == "Ambient temperature"

    def test_piecewise_equation(self, tool):
        """Ternary/piecewise equations work."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="normal(30, 10)"),
                _var(
                    "Y",
                    role="target",
                    equation="2.0 * sqrt(X - 20) + normal(0, 1) if X > 20 else normal(0, 0.1)",
                ),
            ],
            edges=[("X", "Y")],
        )
        world = tool.generate(spec)
        df = world.sample(100, seed=0)
        assert not df["Y"].isna().any()

    def test_complex_real_world(self, tool):
        """A realistic ecology-inspired SCM."""
        spec = SCMSpec(
            variables=[
                _var("rainfall", equation="normal(800, 200)", unit="mm/year"),
                _var("soil_quality", equation="uniform(0.2, 0.9)"),
                _var(
                    "vegetation",
                    equation=(
                        "0.3 * soil_quality + 0.001 * rainfall "
                        "+ normal(0, 0.1)"
                    ),
                ),
                _var(
                    "erosion",
                    role="target",
                    equation=(
                        "max(0, 1.5 - 2.0 * vegetation "
                        "- 0.0005 * rainfall) + normal(0, 0.1)"
                    ),
                    unit="tons/hectare",
                ),
            ],
            edges=[
                ("rainfall", "vegetation"),
                ("soil_quality", "vegetation"),
                ("vegetation", "erosion"),
                ("rainfall", "erosion"),
            ],
        )
        world = tool.generate(spec)
        assert len(world.variables) == 4


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


class TestValidation:
    def test_nan_equation_rejected(self, tool):
        """Equation that always produces NaN is rejected."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="log(-1)"),  # NaN
                _var("Y", role="target", equation="X + normal(0, 1)"),
            ],
            edges=[("X", "Y")],
        )
        with pytest.raises(ValueError, match="NaN"):
            tool.generate(spec)

    def test_zero_variance_rejected(self, tool):
        """Constant equation (zero variance) is rejected."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="42.0"),
                _var("Y", role="target", equation="X + normal(0, 1)"),
            ],
            edges=[("X", "Y")],
        )
        with pytest.raises(ValueError, match="variance"):
            tool.generate(spec)

    def test_invalid_equation_rejected(self, tool):
        """Syntax error in equation is caught."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="normal(0, 1)"),
                _var("Y", role="target", equation="0.5 *** X"),
            ],
            edges=[("X", "Y")],
        )
        with pytest.raises(ExpressionError, match="Syntax error"):
            tool.generate(spec)

    def test_unsafe_equation_rejected(self, tool):
        """Security violation in equation is caught."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="normal(0, 1)"),
                _var("Y", role="target", equation="__import__('os').getcwd()"),
            ],
            edges=[("X", "Y")],
        )
        with pytest.raises(ExpressionError):
            tool.generate(spec)

    def test_unknown_parent_in_equation(self, tool):
        """Equation references a variable that isn't a parent."""
        spec = SCMSpec(
            variables=[
                _var("A", equation="normal(0, 1)"),
                _var("B", equation="normal(0, 1)"),
                _var("C", role="target", equation="A + B + normal(0, 1)"),
            ],
            edges=[("A", "C")],  # B is NOT a parent of C
        )
        with pytest.raises(ExpressionError, match="Unknown name 'B'"):
            tool.generate(spec)


# ------------------------------------------------------------------
# Integration with other SCM tools
# ------------------------------------------------------------------


class TestIntegration:
    def test_sample_works(self, tool):
        """Generated world produces valid samples."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="normal(0, 1)"),
                _var("Y", role="target", equation="2 * X + normal(0, 0.5)"),
            ],
            edges=[("X", "Y")],
        )
        world = tool.generate(spec)
        df = world.sample(500, seed=0)

        assert len(df) == 500
        assert list(df.columns) == world.variables
        assert not df.isna().any().any()

    def test_interventional_sampling(self, tool):
        """do-operator works on generated world."""
        spec = SCMSpec(
            variables=[
                _var("X", equation="normal(0, 1)"),
                _var("Y", role="target", equation="2 * X + normal(0, 0.1)"),
            ],
            edges=[("X", "Y")],
        )
        world = tool.generate(spec)

        samples_do0 = world.interventional_distribution("Y", do={"X": 0.0}, n=500, seed=0)
        samples_do5 = world.interventional_distribution("Y", do={"X": 5.0}, n=500, seed=0)

        # do(X=5) should shift Y by ~10
        assert np.mean(samples_do5) - np.mean(samples_do0) == pytest.approx(10.0, abs=0.5)

    def test_d_separation(self, tool):
        """Graph queries work on generated world."""
        spec = SCMSpec(
            variables=[
                _var("A", equation="normal(0, 1)"),
                _var("B", equation="0.5 * A + normal(0, 1)"),
                _var("C", role="target", equation="0.3 * B + normal(0, 1)"),
            ],
            edges=[("A", "B"), ("B", "C")],
        )
        world = tool.generate(spec)

        # A and C are d-separated given B
        assert world.is_d_separated("A", "C", {"B"})
        # A and C are NOT d-separated without conditioning
        assert not world.is_d_separated("A", "C")

    def test_with_scm_solver(self, tool):
        """Generated world works with SCMSolver."""
        from sreg.solver.scm_solver import SCMSolver

        spec = SCMSpec(
            variables=[
                _var("X", equation="normal(0, 1)"),
                _var("Y", role="target", equation="3 * X + normal(0, 0.5)"),
            ],
            edges=[("X", "Y")],
        )
        world = tool.generate(spec)
        solver = SCMSolver(world)

        samples = solver.interventional_samples("Y", {"X": 2.0}, n=1000)
        assert np.mean(samples) == pytest.approx(6.0, abs=0.5)

    def test_with_scm_task_gen(self, tool):
        """Generated world works with SCMTaskGenTool."""
        from sreg.tools.scm_task_gen import SCMTaskGenTool

        spec = SCMSpec(
            variables=[
                _var("C", equation="normal(0, 1)"),
                _var("X", equation="0.5 * C + normal(0, 1)"),
                _var(
                    "Y",
                    role="target",
                    equation="0.7 * X + 0.3 * C + normal(0, 1)",
                ),
            ],
            edges=[("C", "X"), ("C", "Y"), ("X", "Y")],
        )
        world = tool.generate(spec)

        task_gen = SCMTaskGenTool()
        bundle = task_gen.generate_all(world, target_node="Y", seed=0)
        assert len(bundle.tasks) > 0
        for t in bundle.tasks.values():
            assert t.correct_answer is not None

    def test_full_pipeline(self, tool):
        """SCMSpec -> SCMWorldGenTool -> SCMTaskGenTool -> SCMProblemBuilder."""
        from sreg.tools.scm_problem_builder import SCMProblemBuilder
        from sreg.tools.scm_task_gen import SCMTaskGenTool

        spec = SCMSpec(
            variables=[
                _var("A", equation="normal(10, 3)"),
                _var("B", equation="0.5 * A + normal(0, 1)"),
                _var(
                    "C",
                    role="target",
                    equation="0.3 * A + 0.7 * B + normal(0, 0.5)",
                ),
            ],
            edges=[("A", "B"), ("A", "C"), ("B", "C")],
        )
        world = tool.generate(spec)

        task_gen = SCMTaskGenTool()
        bundle = task_gen.generate_all(world, target_node="C", seed=0)
        task_list = list(bundle.tasks.values())

        builder = SCMProblemBuilder()
        problem = builder.build(world, tasks=task_list, target="C", seed=0)

        assert problem.target_node == "C"
        assert len(problem.data_assets) > 0
        assert len(problem.available_actions) >= 0
        assert problem.research_question
