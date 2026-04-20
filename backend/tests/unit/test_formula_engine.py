import pytest

from app.services.formula_engine import FormulaError, evaluate_formula, validate_formula


def test_basic_arithmetic() -> None:
    assert evaluate_formula("2 + 3 * 4", {}) == 14.0
    assert evaluate_formula("(2 + 3) * 4", {}) == 20.0


def test_power_caret() -> None:
    assert evaluate_formula("2 ^ 3", {}) == 8.0


def test_variables() -> None:
    assert evaluate_formula("length * height / 32", {"length": 100, "height": 8}) == 25.0


def test_functions() -> None:
    assert evaluate_formula("ceil(2.1)", {}) == 3.0
    assert evaluate_formula("floor(2.9)", {}) == 2.0
    assert evaluate_formula("round(2.6)", {}) == 3.0
    assert evaluate_formula("abs(-5)", {}) == 5.0
    assert evaluate_formula("min(3, 7)", {}) == 3.0
    assert evaluate_formula("max(3, 7)", {}) == 7.0


def test_division_by_zero() -> None:
    with pytest.raises(FormulaError) as ei:
        evaluate_formula("1 / 0", {})
    assert ei.value.code == "DIVISION_BY_ZERO"


def test_unknown_variable() -> None:
    with pytest.raises(FormulaError) as ei:
        evaluate_formula("a + 1", {})
    assert ei.value.code == "UNKNOWN_VARIABLE"


def test_unknown_function() -> None:
    with pytest.raises(FormulaError) as ei:
        evaluate_formula("sqrt(4)", {})
    assert ei.value.code == "UNKNOWN_FUNCTION"


def test_syntax_error() -> None:
    with pytest.raises(FormulaError) as ei:
        evaluate_formula("2 +", {})
    assert ei.value.code == "SYNTAX_ERROR"


def test_validate_ok() -> None:
    assert validate_formula("x * 2", {"x"}) is None


def test_validate_bad() -> None:
    msg = validate_formula("x +", {"x"})
    assert msg is not None
