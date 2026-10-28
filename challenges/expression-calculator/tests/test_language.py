import math

import pytest
from calc import (
    CalculatorError,
    Environment,
    Session,
    evaluate,
    evaluate_node,
    fold_constants,
    format_expression,
    parse,
    parse_statement,
    render_error,
)
from calc.formatter import format_number
from calc.functions import BUILTIN_FUNCTIONS, Function
from calc.nodes import BinaryOp, Call, Negate, Number, Variable
from calc.parser import Assignment
from calc.tokens import TokenKind, tokenize


def test_tokenize_identifiers_and_punctuation():
    kinds = [token.kind for token in tokenize("max(x_1, 2) = y")]
    assert kinds == [
        TokenKind.IDENTIFIER,
        TokenKind.LEFT_PAREN,
        TokenKind.IDENTIFIER,
        TokenKind.COMMA,
        TokenKind.NUMBER,
        TokenKind.RIGHT_PAREN,
        TokenKind.EQUALS,
        TokenKind.IDENTIFIER,
        TokenKind.END,
    ]
    assert tokenize("  ab")[0].position == 2


def test_parse_builds_tree_with_positions():
    tree = parse("1 + f(x, 2)")
    assert tree == BinaryOp("+", Number(1), Call("f", (Variable("x"), Number(2))))
    assert tree.position == 2
    assert tree.right.position == 4


def test_parse_negation_and_calls_without_arguments():
    assert parse("-x") == Negate(Variable("x"))
    assert parse("f()") == Call("f", ())


@pytest.mark.parametrize(
    ("source", "position"),
    [("2 +", 3), ("(1 + 2", 0), ("2 3", 2), ("f(1, 2", 1), ("1 = 2", 2), ("x = ", 4)],
)
def test_syntax_errors_carry_positions(source, position):
    with pytest.raises(CalculatorError) as caught:
        parse_statement(source)
    assert caught.value.position == position


def test_parse_statement_distinguishes_assignment():
    assert parse_statement("x = 1 + 2") == Assignment("x", BinaryOp("+", Number(1), Number(2)))
    assert parse_statement("x + 1") == BinaryOp("+", Variable("x"), Number(1))
    with pytest.raises(CalculatorError):
        parse("x = 1")


def test_error_text_and_rendering():
    error = CalculatorError("Unexpected '3'", 2)
    assert str(error) == "Unexpected '3' at position 2"
    assert render_error("2 3", error) == "Unexpected '3' at position 2\n2 3\n  ^"
    assert render_error("1", CalculatorError("Division by zero")) == "Division by zero"
    assert render_error("1", CalculatorError("End", 9)).endswith("\n1\n ^")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("abs(-3)", 3),
        ("sqrt(16)", 4),
        ("min(4, 2, 8)", 2),
        ("max(1, 5) + 1", 6),
        ("floor(2.7) + ceil(2.1)", 5),
        ("trunc(-2.7)", -2),
        ("round(2.5) + round(-2.5)", 0),
        ("round(1.4)", 1),
        ("ln(e)", 1),
        ("exp(0)", 1),
        ("2 * pi", 2 * math.pi),
    ],
)
def test_builtin_functions_and_constants(expression, expected):
    assert evaluate(expression) == pytest.approx(expected)


@pytest.mark.parametrize(
    "expression",
    ["sqrt(-1)", "ln(0)", "abs()", "abs(1, 2)", "min()", "nope(1)", "y + 1", "exp(1000)"],
)
def test_invalid_names_and_arguments_raise(expression):
    with pytest.raises(CalculatorError):
        evaluate(expression)


def test_function_arity_and_argument_errors_are_positioned():
    with pytest.raises(CalculatorError) as caught:
        evaluate("1 + sqrt(-4)")
    assert caught.value.position == 4
    assert "sqrt()" in caught.value.message
    assert BUILTIN_FUNCTIONS["max"].accepts(5)
    assert not BUILTIN_FUNCTIONS["abs"].accepts(2)
    with pytest.raises(CalculatorError):
        BUILTIN_FUNCTIONS["abs"].apply([math.inf])


def test_evaluation_errors_are_positioned_at_the_operator():
    with pytest.raises(CalculatorError) as caught:
        evaluate("1 + 4 / 0")
    assert caught.value.position == 6
    with pytest.raises(CalculatorError) as caught:
        evaluate("2 * zeta")
    assert caught.value.position == 4


def test_environment_variables_and_constants():
    environment = Environment({"x": 3})
    assert evaluate("x * 2 + 1", environment) == 7
    assert evaluate_node(parse("x"), environment) == 3
    environment.assign("x", 4)
    assert environment.lookup("x") == 4
    assert environment.variables == {"x": 4}
    for name in ("pi", "sqrt", "2x"):
        with pytest.raises(CalculatorError):
            environment.assign(name, 1)


def test_environment_functions_and_copy():
    environment = Environment({"x": 1})
    environment.define_function(Function("double", lambda value: 2 * value, 1, 1))
    assert evaluate("double(x + 1)", environment) == 4
    with pytest.raises(CalculatorError):
        environment.define_function(Function("x", abs, 1, 1))
    clone = environment.copy()
    clone.assign("x", 10)
    assert environment.lookup("x") == 1
    assert evaluate("double(x)", clone) == 20
    with pytest.raises(CalculatorError):
        environment.function("missing")


@pytest.mark.parametrize(
    ("tree", "expected"),
    [
        (BinaryOp("-", BinaryOp("-", Number(1), Number(2)), Number(3)), "1 - 2 - 3"),
        (BinaryOp("-", Number(1), BinaryOp("-", Number(2), Number(3))), "1 - (2 - 3)"),
        (BinaryOp("/", BinaryOp("/", Number(8), Number(4)), Number(2)), "8 / 4 / 2"),
        (BinaryOp("/", Number(8), BinaryOp("*", Number(4), Number(2))), "8 / (4 * 2)"),
        (BinaryOp("^", Number(2), BinaryOp("^", Number(3), Number(2))), "2 ^ 3 ^ 2"),
        (BinaryOp("^", BinaryOp("^", Number(2), Number(3)), Number(2)), "(2 ^ 3) ^ 2"),
        (BinaryOp("^", Number(2), Negate(Number(1))), "2 ^ -1"),
        (BinaryOp("^", Negate(Number(2)), Number(2)), "(-2) ^ 2"),
        (Negate(BinaryOp("^", Number(2), Number(2))), "-2 ^ 2"),
        (Negate(BinaryOp("+", Variable("a"), Number(1))), "-(a + 1)"),
        (BinaryOp("*", BinaryOp("+", Number(1), Number(2)), Number(3)), "(1 + 2) * 3"),
        (BinaryOp("*", Number(2), Negate(Number(3))), "2 * -3"),
        (Call("max", (Variable("a"), Number(0.5))), "max(a, 0.5)"),
    ],
)
def test_format_expression_uses_minimal_parentheses(tree, expected):
    assert format_expression(tree) == expected


@pytest.mark.parametrize(
    "source", ["1 + 2 * 3", "(1 + 2) * 3", "10 - (4 - 3)", "-(x + 1) * f(y, 2)", "-2 ^ 2"]
)
def test_format_expression_round_trips(source):
    tree = parse(source)
    assert parse(format_expression(tree)) == tree


@pytest.mark.parametrize(
    ("value", "expected"),
    [(3.0, "3"), (0.5, "0.5"), (1e-05, "0.00001"), (1e16, "10000000000000000"), (-2.0, "-2")],
)
def test_format_number(value, expected):
    assert format_number(value) == expected


def test_format_number_rejects_non_finite_values():
    with pytest.raises(CalculatorError):
        format_number(math.inf)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("1 + 2 * 3", "7"),
        ("x + 2 * 3", "x + 6"),
        ("x * (2 - 5)", "x * -3"),
        ("-(2 + 3) + y", "-5 + y"),
        ("sqrt(9) + x", "3 + x"),
        ("max(x, 1 + 1)", "max(x, 2)"),
        ("unknown(1 + 1)", "unknown(2)"),
        ("x + 1 / 0", "x + 1 / 0"),
        ("sqrt(-4)", "sqrt(-4)"),
        ("--3", "3"),
    ],
)
def test_fold_constants(source, expected):
    assert format_expression(fold_constants(parse(source))) == expected


def test_fold_constants_preserves_positions_and_values():
    folded = fold_constants(parse("x + (1 + 2)"))
    assert folded == BinaryOp("+", Variable("x"), Number(3))
    assert folded.right.position == 7
    environment = Environment({"x": 2.5})
    tree = parse("x * (3 - 1) + sqrt(4) - 7 % 4")
    assert evaluate_node(fold_constants(tree), environment) == evaluate_node(tree, environment)


def test_session_assignments_and_ans():
    session = Session()
    assert session.execute("x = 2 + 3") == 5
    assert session.execute("x * 2") == 10
    assert session.execute("ans + 1") == 11
    assert session.environment.variables == {"x": 5, "ans": 11}
    assert [entry.source for entry in session.history] == ["x = 2 + 3", "x * 2", "ans + 1"]


def test_session_failed_lines_change_nothing():
    session = Session(Environment({"x": 1}))
    for line in ("pi = 3", "x = 1 / 0", "x +", "ans"):
        with pytest.raises(CalculatorError):
            session.execute(line)
    assert session.environment.variables == {"x": 1}
    assert session.history == ()


def test_session_run_formats_results_and_errors():
    session = Session()
    assert session.run("r = 1.5") == "r = 1.5"
    assert session.run("r * 4") == "6"
    assert session.run("r +") == "Unexpected end of expression at position 3\nr +\n   ^"
    assert session.run("1 / 0") == "Division by zero at position 2\n1 / 0\n  ^"
    assert len(session.history) == 2


def test_session_simplify():
    session = Session(Environment({"x": 4}))
    assert session.simplify("x * (1 + 1) - 0.5") == "x * 2 - 0.5"
