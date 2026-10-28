import pytest
from calc import CalculatorError, evaluate


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("10 - 4 - 3", 3),
        ("2 + 3 ^ 2", 11),
        ("-2 ^ 2", -4),
        ("-(3 - 5)", 2),
        ("2 * -3", -6),
        (".5 + 1.25", 1.75),
        ("  7  ", 7),
    ],
)
def test_basic_arithmetic(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("8 / 4 / 2", 1), ("2 * 3 % 4", 2), ("12 / 3 * 2", 8)],
)
def test_multiplicative_operators_are_left_associative(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("2 ^ 3 ^ 2", 512), ("2 ^ -1", 0.5), ("4 ^ -(1 - 1.5)", 2)],
)
def test_exponent_is_right_associative_and_accepts_unary_minus(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [("-7 % 3", -1), ("7 % -3", 1), ("7.5 % 2", 1.5)],
)
def test_remainder_takes_sign_of_dividend(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expression",
    ["1 / 0", "5 % 0", "2 +", "(1 + 2", "2 3", "1.2.3", "2 $ 3", "10 ^ 400", ")"],
)
def test_invalid_expressions_raise(expression):
    with pytest.raises(CalculatorError):
        evaluate(expression)
