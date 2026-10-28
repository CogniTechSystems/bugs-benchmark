"""Name resolution for the variables, constants and functions visible to expressions."""

from collections.abc import Mapping

from calc.errors import CalculatorError
from calc.functions import BUILTIN_FUNCTIONS, CONSTANTS, Function


class Environment:
    """The constants, built-in functions and assigned variables visible to an expression, where
    constant and function names cannot be reassigned.
    """

    def __init__(self, variables: Mapping[str, float] | None = None) -> None:
        """Create an environment holding the constants and built-in functions, then assign each
        supplied variable in order.
        """
        self._variables: dict[str, float] = {}
        self._functions: dict[str, Function] = dict(BUILTIN_FUNCTIONS)
        for name, value in (variables or {}).items():
            self.assign(name, value)

    @property
    def variables(self) -> dict[str, float]:
        """Return a copy of the assigned variables, excluding constants and functions."""
        return dict(self._variables)

    def lookup(self, name: str, position: int | None = None) -> float:
        """Return the value of a constant or variable, checking constants first, and raise a
        positioned error when the name is undefined.
        """
        if name in CONSTANTS:
            return CONSTANTS[name]
        if name in self._variables:
            return self._variables[name]
        raise CalculatorError(f"Undefined variable {name!r}", position)

    def assign(self, name: str, value: float) -> None:
        """Bind a valid identifier to a float value, replacing any earlier binding, and reject names
        used by constants or functions.
        """
        if not name.isidentifier():
            raise CalculatorError(f"Invalid variable name {name!r}")
        if name in CONSTANTS or name in self._functions:
            raise CalculatorError(f"Cannot assign to {name!r}")
        self._variables[name] = float(value)

    def define_function(self, function: Function) -> None:
        """Register a function under its name, replacing any function of that name, and reject names
        used by constants or variables.
        """
        if function.name in CONSTANTS or function.name in self._variables:
            raise CalculatorError(f"Name {function.name!r} is already in use")
        self._functions[function.name] = function

    def function(self, name: str, position: int | None = None) -> Function:
        """Return the function registered under a name, raising a positioned error when no such
        function exists.
        """
        if name not in self._functions:
            raise CalculatorError(f"Unknown function {name!r}", position)
        return self._functions[name]

    def copy(self) -> "Environment":
        """Return an independent environment holding copies of the variables and functions."""
        clone = Environment()
        clone._variables = dict(self._variables)
        clone._functions = dict(self._functions)
        return clone
