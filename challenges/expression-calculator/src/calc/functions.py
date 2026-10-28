"""Built-in functions and constants available to every expression."""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from calc.errors import CalculatorError


@dataclass(frozen=True)
class Function:
    """A named numeric function with a positional implementation and an inclusive arity range whose
    upper bound may be unlimited.
    """

    name: str
    implementation: Callable[..., float]
    minimum_arity: int
    maximum_arity: int | None

    def accepts(self, count: int) -> bool:
        """Return whether the argument count lies within the inclusive arity range, treating a
        missing maximum as unbounded.
        """
        if count < self.minimum_arity:
            return False
        return self.maximum_arity is None or count <= self.maximum_arity

    def apply(self, arguments: Sequence[float], position: int | None = None) -> float:
        """Call the implementation with finite arguments and return a float, raising a positioned
        error for bad arity, non-finite arguments, rejection or overflow.
        """
        if not self.accepts(len(arguments)):
            raise CalculatorError(
                f"{self.name}() does not take {len(arguments)} argument(s)", position
            )
        if not all(math.isfinite(argument) for argument in arguments):
            raise CalculatorError(f"{self.name}() requires finite arguments", position)
        try:
            return float(self.implementation(*arguments))
        except CalculatorError as error:
            raise CalculatorError(f"{self.name}() {error.message}", position) from None
        except OverflowError:
            raise CalculatorError(f"{self.name}() result is too large", position) from None


def _sqrt(value: float) -> float:
    """Return the non-negative square root, rejecting negative arguments."""
    if value < 0:
        raise CalculatorError("requires a non-negative argument")
    return math.sqrt(value)


def _ln(value: float) -> float:
    """Return the natural logarithm, rejecting arguments that are zero or negative."""
    if value <= 0:
        raise CalculatorError("requires a positive argument")
    return math.log(value)


def _round(value: float) -> float:
    """Round to the nearest integer, rounding halves away from zero."""
    return math.copysign(math.floor(abs(value) + 0.5), value)


BUILTIN_FUNCTIONS: dict[str, Function] = {
    function.name: function
    for function in (
        Function("abs", abs, 1, 1),
        Function("sqrt", _sqrt, 1, 1),
        Function("exp", math.exp, 1, 1),
        Function("ln", _ln, 1, 1),
        Function("floor", math.floor, 1, 1),
        Function("ceil", math.ceil, 1, 1),
        Function("trunc", math.trunc, 1, 1),
        Function("round", _round, 1, 1),
        Function("min", min, 1, None),
        Function("max", max, 1, None),
    )
}

CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e}
