"""Rendering of syntax trees back to canonical source text."""

import math
from decimal import Decimal

from calc.errors import CalculatorError
from calc.grammar import ATOM_PRECEDENCE, BINARY_OPERATORS, NEGATION_PRECEDENCE, Associativity
from calc.nodes import BinaryOp, Call, Negate, Node, Number, Variable


def format_expression(node: Node) -> str:
    """Render a tree as spaced canonical source, parenthesising operands that bind looser, or
    equally on the side opposite associativity, except negated exponents.
    """
    if isinstance(node, Number):
        return format_number(node.value)
    if isinstance(node, Variable):
        return node.name
    if isinstance(node, Negate):
        return "-" + _operand(node.operand, precedence(node.operand) < NEGATION_PRECEDENCE)
    if isinstance(node, Call):
        arguments = ", ".join(format_expression(argument) for argument in node.arguments)
        return f"{node.name}({arguments})"
    operator = BINARY_OPERATORS[node.operator]
    left_precedence = precedence(node.left)
    right_precedence = precedence(node.right)
    left_parenthesised = left_precedence < operator.precedence or (
        left_precedence == operator.precedence and operator.associativity is Associativity.RIGHT
    )
    right_parenthesised = right_precedence < operator.precedence or (
        right_precedence == operator.precedence and operator.associativity is Associativity.LEFT
    )
    if node.operator == "^" and isinstance(node.right, Negate):
        right_parenthesised = False
    left = _operand(node.left, left_parenthesised)
    right = _operand(node.right, right_parenthesised)
    return f"{left} {node.operator} {right}"


def format_number(value: float) -> str:
    """Render a finite float in plain decimal notation, integral values without a fraction and
    others with shortest round-trip digits.
    """
    if not math.isfinite(value):
        raise CalculatorError("Result is not a finite number")
    if value.is_integer():
        return str(int(value))
    return format(Decimal(repr(value)), "f")


def precedence(node: Node) -> int:
    """Return the binding level of a node as an operand, with literals, variables and calls sharing
    the highest level.
    """
    if isinstance(node, BinaryOp):
        return BINARY_OPERATORS[node.operator].precedence
    if isinstance(node, Negate):
        return NEGATION_PRECEDENCE
    return ATOM_PRECEDENCE


def _operand(node: Node, parenthesised: bool) -> str:
    """Format a node as source text, wrapped in parentheses when requested."""
    text = format_expression(node)
    return f"({text})" if parenthesised else text
