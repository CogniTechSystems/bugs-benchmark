"""Syntax tree node types produced by the parser, compared structurally without source positions."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Number:
    """A numeric literal whose value is finite and not negative."""

    value: float
    position: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Variable:
    """A reference to a variable by name."""

    name: str
    position: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Negate:
    """Prefix negation of a single operand."""

    operand: "Node"
    position: int = field(default=0, compare=False)


@dataclass(frozen=True)
class BinaryOp:
    """A binary operator applied to left and right operands, positioned at the operator."""

    operator: str
    left: "Node"
    right: "Node"
    position: int = field(default=0, compare=False)


@dataclass(frozen=True)
class Call:
    """A call of a named function with positional argument nodes."""

    name: str
    arguments: tuple["Node", ...]
    position: int = field(default=0, compare=False)


Node = Number | Variable | Negate | BinaryOp | Call
