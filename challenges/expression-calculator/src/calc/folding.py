"""Constant folding of syntax trees."""

import math
from collections.abc import Callable, Mapping

from calc.errors import CalculatorError
from calc.evaluator import apply_binary
from calc.functions import BUILTIN_FUNCTIONS, Function
from calc.nodes import BinaryOp, Call, Negate, Node, Number


def fold_constants(node: Node, functions: Mapping[str, Function] = BUILTIN_FUNCTIONS) -> Node:
    """Return an equivalent tree with variable-free subexpressions calling only known functions
    replaced by finite literals, keeping failing subexpressions and original positions.
    """
    if isinstance(node, Negate):
        operand = fold_constants(node.operand, functions)
        value = constant_value(operand)
        if value is not None:
            return literal(-value, node.position)
        return Negate(operand, node.position)
    if isinstance(node, BinaryOp):
        left = fold_constants(node.left, functions)
        right = fold_constants(node.right, functions)
        folded = BinaryOp(node.operator, left, right, node.position)
        left_value, right_value = constant_value(left), constant_value(right)
        if left_value is None or right_value is None:
            return folded
        return _fold(folded, lambda: apply_binary(node.operator, left_value, right_value))
    if isinstance(node, Call):
        arguments = tuple(fold_constants(argument, functions) for argument in node.arguments)
        folded_call = Call(node.name, arguments, node.position)
        function = functions.get(node.name)
        values = [constant_value(argument) for argument in arguments]
        constants = [value for value in values if value is not None]
        if function is None or len(constants) != len(values):
            return folded_call
        return _fold(folded_call, lambda: function.apply(constants))
    return node


def constant_value(node: Node) -> float | None:
    """Return the value of a literal or negated literal, or nothing for any other node."""
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Negate) and isinstance(node.operand, Number):
        return -node.operand.value
    return None


def literal(value: float, position: int = 0) -> Node:
    """Return the canonical node for a finite value, a literal negated when its sign bit is set."""
    if math.copysign(1.0, value) < 0:
        return Negate(Number(-value, position), position)
    return Number(value, position)


def _fold(original: Node, compute: Callable[[], float]) -> Node:
    """Return the literal for the computed value, or the original node when computation fails or is
    not finite.
    """
    try:
        value = compute()
    except CalculatorError:
        return original
    if not math.isfinite(value):
        return original
    return literal(value, original.position)
