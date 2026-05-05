"""Tests for ExpressionCompiler: correctness + security."""

import numpy as np
import pytest

from sreg.world.expression_compiler import ExpressionCompiler, ExpressionError


@pytest.fixture
def compiler():
    return ExpressionCompiler()


@pytest.fixture
def rng():
    return np.random.default_rng(42)


# ------------------------------------------------------------------
# Basic correctness
# ------------------------------------------------------------------


class TestArithmetic:
    def test_constant(self, compiler, rng):
        eq = compiler.compile_equation("42.0", [])
        assert eq({}, rng) == 42.0

    def test_integer_constant(self, compiler, rng):
        eq = compiler.compile_equation("7", [])
        assert eq({}, rng) == 7.0

    def test_addition(self, compiler, rng):
        eq = compiler.compile_equation("A + B", ["A", "B"])
        assert eq({"A": 3.0, "B": 4.0}, rng) == 7.0

    def test_multiplication(self, compiler, rng):
        eq = compiler.compile_equation("0.5 * X", ["X"])
        assert eq({"X": 10.0}, rng) == 5.0

    def test_complex_arithmetic(self, compiler, rng):
        eq = compiler.compile_equation("0.5 * X + 0.3 * Y - 2", ["X", "Y"])
        result = eq({"X": 10.0, "Y": 20.0}, rng)
        assert result == pytest.approx(9.0)

    def test_power(self, compiler, rng):
        eq = compiler.compile_equation("X ** 2", ["X"])
        assert eq({"X": 3.0}, rng) == 9.0

    def test_unary_minus(self, compiler, rng):
        eq = compiler.compile_equation("-X", ["X"])
        assert eq({"X": 5.0}, rng) == -5.0

    def test_division(self, compiler, rng):
        eq = compiler.compile_equation("X / 2", ["X"])
        assert eq({"X": 10.0}, rng) == 5.0

    def test_floor_division(self, compiler, rng):
        eq = compiler.compile_equation("X // 3", ["X"])
        assert eq({"X": 10.0}, rng) == 3.0

    def test_modulo(self, compiler, rng):
        eq = compiler.compile_equation("X % 3", ["X"])
        assert eq({"X": 10.0}, rng) == 1.0


class TestMathFunctions:
    def test_exp(self, compiler, rng):
        eq = compiler.compile_equation("exp(X)", ["X"])
        assert eq({"X": 0.0}, rng) == pytest.approx(1.0)

    def test_log(self, compiler, rng):
        eq = compiler.compile_equation("log(X)", ["X"])
        assert eq({"X": 1.0}, rng) == pytest.approx(0.0)

    def test_sqrt(self, compiler, rng):
        eq = compiler.compile_equation("sqrt(X)", ["X"])
        assert eq({"X": 9.0}, rng) == pytest.approx(3.0)

    def test_sin_cos(self, compiler, rng):
        eq = compiler.compile_equation("sin(X) + cos(X)", ["X"])
        assert eq({"X": 0.0}, rng) == pytest.approx(1.0)

    def test_abs(self, compiler, rng):
        eq = compiler.compile_equation("abs(X)", ["X"])
        assert eq({"X": -5.0}, rng) == 5.0

    def test_min_max(self, compiler, rng):
        eq = compiler.compile_equation("min(X, Y)", ["X", "Y"])
        assert eq({"X": 3.0, "Y": 7.0}, rng) == 3.0

        eq2 = compiler.compile_equation("max(X, Y)", ["X", "Y"])
        assert eq2({"X": 3.0, "Y": 7.0}, rng) == 7.0

    def test_pow_function(self, compiler, rng):
        eq = compiler.compile_equation("pow(X, 3)", ["X"])
        assert eq({"X": 2.0}, rng) == 8.0

    def test_nested_functions(self, compiler, rng):
        eq = compiler.compile_equation("exp(-0.5 * pow(X / 5, 2))", ["X"])
        result = eq({"X": 0.0}, rng)
        assert result == pytest.approx(1.0)

    def test_log2_log10(self, compiler, rng):
        eq = compiler.compile_equation("log2(X)", ["X"])
        assert eq({"X": 8.0}, rng) == pytest.approx(3.0)

        eq2 = compiler.compile_equation("log10(X)", ["X"])
        assert eq2({"X": 100.0}, rng) == pytest.approx(2.0)


class TestDistributions:
    def test_normal(self, compiler, rng):
        eq = compiler.compile_equation("normal(0, 1)", [])
        values = [eq({}, np.random.default_rng(i)) for i in range(100)]
        assert abs(np.mean(values)) < 0.5  # rough check
        assert np.std(values) > 0.3

    def test_uniform(self, compiler, rng):
        eq = compiler.compile_equation("uniform(10, 20)", [])
        values = [eq({}, np.random.default_rng(i)) for i in range(100)]
        assert all(10 <= v <= 20 for v in values)

    def test_exponential(self, compiler, rng):
        eq = compiler.compile_equation("exponential(2.0)", [])
        values = [eq({}, np.random.default_rng(i)) for i in range(100)]
        assert all(v >= 0 for v in values)

    def test_lognormal(self, compiler, rng):
        eq = compiler.compile_equation("lognormal(0, 0.5)", [])
        values = [eq({}, np.random.default_rng(i)) for i in range(100)]
        assert all(v > 0 for v in values)

    def test_beta(self, compiler, rng):
        eq = compiler.compile_equation("beta(2, 5)", [])
        values = [eq({}, np.random.default_rng(i)) for i in range(100)]
        assert all(0 <= v <= 1 for v in values)

    def test_gamma(self, compiler, rng):
        eq = compiler.compile_equation("gamma(2, 3)", [])
        values = [eq({}, np.random.default_rng(i)) for i in range(100)]
        assert all(v >= 0 for v in values)

    def test_distribution_with_parent(self, compiler):
        """Distribution parameters can reference parent variables."""
        eq = compiler.compile_equation("normal(X, 0.1)", ["X"])
        values = [eq({"X": 50.0}, np.random.default_rng(i)) for i in range(100)]
        assert abs(np.mean(values) - 50.0) < 1.0


class TestPiecewise:
    def test_ternary(self, compiler, rng):
        eq = compiler.compile_equation("2 * X if X > 0 else -X", ["X"])
        assert eq({"X": 5.0}, rng) == 10.0
        assert eq({"X": -3.0}, rng) == 3.0

    def test_comparison_operators(self, compiler, rng):
        eq = compiler.compile_equation("1.0 if X >= 10 else 0.0", ["X"])
        assert eq({"X": 10.0}, rng) == 1.0
        assert eq({"X": 9.0}, rng) == 0.0

    def test_boolean_and(self, compiler, rng):
        eq = compiler.compile_equation(
            "1.0 if X > 0 and Y > 0 else 0.0", ["X", "Y"]
        )
        assert eq({"X": 1.0, "Y": 1.0}, rng) == 1.0
        assert eq({"X": -1.0, "Y": 1.0}, rng) == 0.0

    def test_threshold_with_math(self, compiler, rng):
        eq = compiler.compile_equation(
            "2.0 * sqrt(X - 7) if X > 7 else 0.3 * X", ["X"]
        )
        assert eq({"X": 11.0}, rng) == pytest.approx(4.0)
        assert eq({"X": 5.0}, rng) == pytest.approx(1.5)


class TestReproducibility:
    def test_same_seed_same_result(self, compiler):
        eq = compiler.compile_equation("X + normal(0, 1)", ["X"])
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)
        v1 = eq({"X": 10.0}, rng1)
        v2 = eq({"X": 10.0}, rng2)
        assert v1 == v2

    def test_different_seed_different_result(self, compiler):
        eq = compiler.compile_equation("normal(0, 1)", [])
        rng1 = np.random.default_rng(1)
        rng2 = np.random.default_rng(2)
        v1 = eq({}, rng1)
        v2 = eq({}, rng2)
        assert v1 != v2


# ------------------------------------------------------------------
# Security
# ------------------------------------------------------------------


class TestSecurity:
    def test_import_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Unknown function"):
            compiler.compile_equation("__import__('os')", [])

    def test_attribute_access_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Disallowed"):
            compiler.compile_equation("X.__class__", ["X"])

    def test_string_constant_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="numeric constants"):
            compiler.compile_equation("'hello'", [])

    def test_list_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Disallowed"):
            compiler.compile_equation("[1, 2, 3]", [])

    def test_dict_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Disallowed"):
            compiler.compile_equation("{'a': 1}", [])

    def test_lambda_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="simple function calls"):
            compiler.compile_equation("(lambda x: x)(5)", [])

    def test_comprehension_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Disallowed"):
            compiler.compile_equation("[x for x in range(10)]", [])

    def test_method_call_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="methods"):
            compiler.compile_equation("X.bit_length()", ["X"])

    def test_subscript_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Disallowed"):
            compiler.compile_equation("X[0]", ["X"])

    def test_unknown_name_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Unknown name"):
            compiler.compile_equation("X + secret", ["X"])

    def test_unknown_function_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="Unknown function"):
            compiler.compile_equation("eval('1+1')", [])

    def test_builtin_access_blocked(self, compiler):
        with pytest.raises(ExpressionError):
            compiler.compile_equation("print(1)", [])

    def test_empty_expression(self, compiler):
        with pytest.raises(ExpressionError, match="Empty"):
            compiler.compile_equation("", [])

    def test_syntax_error(self, compiler):
        with pytest.raises(ExpressionError, match="Syntax error"):
            compiler.compile_equation("2 +* 3", [])

    def test_boolean_constant_rejected(self, compiler):
        with pytest.raises(ExpressionError, match="numeric constants"):
            compiler.compile_equation("True", [])


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestEdgeCases:
    def test_root_equation_no_parents(self, compiler, rng):
        """Root nodes have no parents -- equation only uses distributions."""
        eq = compiler.compile_equation("normal(25, 5)", [])
        value = eq({}, rng)
        assert isinstance(value, float)

    def test_whitespace_handling(self, compiler, rng):
        eq = compiler.compile_equation("  0.5 * X + 3  ", ["X"])
        assert eq({"X": 10.0}, rng) == 8.0

    def test_deeply_nested(self, compiler, rng):
        expr = "max(0, min(100, exp(-0.5 * pow((X - 50) / 10, 2)) * 100))"
        eq = compiler.compile_equation(expr, ["X"])
        result = eq({"X": 50.0}, rng)
        assert result == pytest.approx(100.0)

    def test_doc_preserved(self, compiler):
        eq = compiler.compile_equation("X + 1", ["X"])
        assert eq.__doc__ == "X + 1"

    def test_numpy_robustness_exp_large(self, compiler, rng):
        """exp(large) returns inf instead of raising OverflowError."""
        eq = compiler.compile_equation("exp(X)", ["X"])
        result = eq({"X": 1000.0}, rng)
        assert np.isinf(result)

    def test_numpy_robustness_log_negative(self, compiler, rng):
        """log(negative) returns nan instead of raising ValueError."""
        eq = compiler.compile_equation("log(X)", ["X"])
        result = eq({"X": -1.0}, rng)
        assert np.isnan(result)


# ------------------------------------------------------------------
# v1.5 additions: bernoulli, sigmoid, I (indicator)
# ------------------------------------------------------------------


class TestBernoulli:
    def test_bernoulli_in_zero_one(self, compiler, rng):
        eq = compiler.compile_equation("bernoulli(0.5)", [])
        for _ in range(20):
            v = eq({}, rng)
            assert v in (0.0, 1.0)

    def test_bernoulli_p_zero_returns_zero(self, compiler, rng):
        eq = compiler.compile_equation("bernoulli(0.0)", [])
        for _ in range(10):
            assert eq({}, rng) == 0.0

    def test_bernoulli_p_one_returns_one(self, compiler, rng):
        eq = compiler.compile_equation("bernoulli(1.0)", [])
        for _ in range(10):
            assert eq({}, rng) == 1.0

    def test_bernoulli_uses_rng(self, compiler):
        """bernoulli sampling es reproducible con misma seed."""
        eq = compiler.compile_equation("bernoulli(0.5)", [])
        samples_a = [eq({}, np.random.default_rng(7)) for _ in range(5)]
        samples_b = [eq({}, np.random.default_rng(7)) for _ in range(5)]
        # Cada llamada con un rng fresco produce el primer sample.
        assert samples_a == samples_b

    def test_bernoulli_p_out_of_range_raises_at_runtime(self, compiler, rng):
        """p fuera de [0, 1] no es detectable en compile-time (puede ser
        expresión sobre padres). Falla en runtime al evaluar."""
        eq = compiler.compile_equation("bernoulli(2.0)", [])
        with pytest.raises(ValueError):
            eq({}, rng)
        eq_neg = compiler.compile_equation("bernoulli(-0.5)", [])
        with pytest.raises(ValueError):
            eq_neg({}, rng)


class TestSigmoid:
    def test_sigmoid_zero_is_half(self, compiler, rng):
        eq = compiler.compile_equation("sigmoid(0)", [])
        assert eq({}, rng) == pytest.approx(0.5)

    def test_sigmoid_large_positive_approaches_one(self, compiler, rng):
        eq = compiler.compile_equation("sigmoid(20)", [])
        assert eq({}, rng) > 0.9999

    def test_sigmoid_large_negative_approaches_zero(self, compiler, rng):
        eq = compiler.compile_equation("sigmoid(-20)", [])
        assert eq({}, rng) < 0.0001

    def test_sigmoid_with_parent(self, compiler, rng):
        eq = compiler.compile_equation("sigmoid(2 * X - 1)", ["X"])
        # sigmoid(2*0.5 - 1) = sigmoid(0) = 0.5
        assert eq({"X": 0.5}, rng) == pytest.approx(0.5)


class TestIndicator:
    def test_indicator_true(self, compiler, rng):
        eq = compiler.compile_equation("I(X < 2500)", ["X"])
        assert eq({"X": 2000.0}, rng) == 1.0

    def test_indicator_false(self, compiler, rng):
        eq = compiler.compile_equation("I(X < 2500)", ["X"])
        assert eq({"X": 3000.0}, rng) == 0.0

    def test_indicator_chained_conditions(self, compiler, rng):
        eq = compiler.compile_equation("I(X > 0)", ["X"])
        assert eq({"X": 5.0}, rng) == 1.0
        assert eq({"X": -1.0}, rng) == 0.0


class TestBirthWeightParadoxExpressions:
    """Verifica que las expresiones del caso BWP compilan y se ejecutan.

    Ver `research/examples/birth_weight_paradox.md`.
    """

    def test_smoking_bernoulli(self, compiler, rng):
        eq = compiler.compile_equation("bernoulli(0.30)", [])
        # Sample varias veces; debe estar en {0, 1}.
        for _ in range(50):
            assert eq({}, rng) in (0.0, 1.0)

    def test_birth_weight_linear(self, compiler, rng):
        expr = "3200 - 250*Smoking - 1000*HiddenU + normal(0, 380)"
        eq = compiler.compile_equation(expr, ["Smoking", "HiddenU"])
        # No-fumadora, no-confounder: ~ 3200 ± 380.
        v = eq({"Smoking": 0.0, "HiddenU": 0.0}, rng)
        assert 1000 < v < 5000

    def test_low_bw_indicator(self, compiler, rng):
        eq = compiler.compile_equation("I(BirthWeight < 2500)", ["BirthWeight"])
        assert eq({"BirthWeight": 2000.0}, rng) == 1.0
        assert eq({"BirthWeight": 3500.0}, rng) == 0.0

    def test_mortality_logistic(self, compiler, rng):
        expr = "bernoulli(sigmoid(-2.5 + 2.8*HiddenU - 0.0030*(BirthWeight - 3000)))"
        eq = compiler.compile_equation(expr, ["HiddenU", "BirthWeight"])
        # No-confounder, peso normal: probabilidad muy baja.
        zeros = sum(
            eq({"HiddenU": 0.0, "BirthWeight": 3200.0}, rng) == 0.0
            for _ in range(200)
        )
        # sigmoid(-2.5 - 0.6) ≈ 0.04 → ~96% deberían ser 0.
        assert zeros >= 180
