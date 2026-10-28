"""Operator precedence and associativity definitions for the expression language."""

from dataclasses import dataclass
from enum import Enum


class Associativity(Enum):
    """The direction in which a chain of operators of equal precedence is grouped."""

    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class BinaryOperator:
    """Static description of a binary operator, where a higher precedence binds more tightly."""

    symbol: str
    precedence: int
    associativity: Associativity


BINARY_OPERATORS: dict[str, BinaryOperator] = {
    operator.symbol: operator
    for operator in (
        BinaryOperator("+", 1, Associativity.LEFT),
        BinaryOperator("-", 1, Associativity.LEFT),
        BinaryOperator("*", 2, Associativity.LEFT),
        BinaryOperator("/", 2, Associativity.LEFT),
        BinaryOperator("%", 2, Associativity.LEFT),
        BinaryOperator("^", 4, Associativity.RIGHT),
    )
}

NEGATION_PRECEDENCE = 3
ATOM_PRECEDENCE = 5
