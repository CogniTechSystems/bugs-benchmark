"""Numeric evaluation of parsed expressions using double precision floats."""

import math

from calc.environment import Environment
from calc.errors import CalculatorError
from calc.nodes import Call, Negate, Node, Number, Variable
from calc.parser import parse


def evaluate(source: str, environment: Environment | None = None) -> float:
    """Parse and evaluate source text against an optional environment, raising an error for syntax
    faults, undefined names, invalid arithmetic or non-finite results.
    """
    return evaluate_node(parse(source), environment)


def evaluate_node(node: Node, environment: Environment | None = None) -> float:
    """Evaluate a syntax tree against an optional environment and return its value, which must be
    finite.
    """
    value = _evaluate(node, environment or Environment())
    if not math.isfinite(value):
        raise CalculatorError("Result is not a finite number", node.position)
    return value


def apply_binary(operator: str, left: float, right: float) -> float:
    """Apply an addition, subtraction, multiplication, division, remainder or exponentiation
    operator to two floats, raising an unpositioned error when undefined.
    """
    if operator == "+":
        return left + right
    if operator == "-":
        return left - right
    if operator == "^":
        return _raise_to_power(left, right)
    return _multiplicative(operator, left, right)


def _evaluate(node: Node, environment: Environment) -> float:
    """Recursively evaluate a node, repositioning arithmetic errors at the failing node and allowing
    infinite intermediate values.
    """
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Variable):
        return environment.lookup(node.name, node.position)
    if isinstance(node, Negate):
        return -_evaluate(node.operand, environment)
    if isinstance(node, Call):
        function = environment.function(node.name, node.position)
        arguments = [_evaluate(argument, environment) for argument in node.arguments]
        return function.apply(arguments, node.position)
    left = _evaluate(node.left, environment)
    right = _evaluate(node.right, environment)
    try:
        return apply_binary(node.operator, left, right)
    except CalculatorError as error:
        raise CalculatorError(error.message, node.position) from None


def _multiplicative(operator: str, left: float, right: float) -> float:
    """Return the product, true quotient or truncated remainder carrying the dividend's sign,
    raising an error for a zero divisor.
    """
    if operator == "*":
        return left * right
    if right == 0:
        raise CalculatorError("Division by zero")
    if operator == "/":
        return left / right
    return left % right


def _raise_to_power(base: float, exponent: float) -> float:
    """Return the base raised to a real exponent, raising an error for zero to a negative power,
    complex results or overflow.
    """
    try:
        result = base**exponent
    except ZeroDivisionError:
        raise CalculatorError("Zero cannot be raised to a negative power") from None
    except OverflowError:
        raise CalculatorError("Result is too large") from None
    if isinstance(result, complex):
        raise CalculatorError("Result is not a real number")
    return result
