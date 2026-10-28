"""Interactive calculator sessions with a shared environment and history."""

from dataclasses import dataclass

from calc.environment import Environment
from calc.errors import CalculatorError, render_error
from calc.evaluator import evaluate_node
from calc.folding import fold_constants
from calc.formatter import format_expression, format_number
from calc.parser import Assignment, Statement, parse, parse_statement


@dataclass(frozen=True)
class HistoryEntry:
    """A successfully executed line paired with the value it produced."""

    source: str
    value: float


class Session:
    """Lines evaluated against a shared environment, where each success is stored as the ans
    variable and recorded, and each failure changes nothing.
    """

    def __init__(self, environment: Environment | None = None) -> None:
        """Start a session with the given environment, or a fresh one when none is given."""
        self._environment = environment or Environment()
        self._history: list[HistoryEntry] = []

    @property
    def environment(self) -> Environment:
        """Return the environment in which lines are evaluated."""
        return self._environment

    @property
    def history(self) -> tuple[HistoryEntry, ...]:
        """Return the successfully executed lines, oldest first."""
        return tuple(self._history)

    def execute(self, line: str) -> float:
        """Execute an expression or assignment line and return its value, raising an error when
        parsing, evaluation or assignment fails.
        """
        return self._execute(parse_statement(line), line)

    def run(self, line: str) -> str:
        """Execute a line and return its display text, prefixing assignments with their name and
        rendering errors instead of raising them.
        """
        try:
            statement = parse_statement(line)
            value = self._execute(statement, line)
        except CalculatorError as error:
            return render_error(line, error)
        if isinstance(statement, Assignment):
            return f"{statement.name} = {format_number(value)}"
        return format_number(value)

    def simplify(self, line: str) -> str:
        """Return the canonical text of an expression after constant folding, leaving variables
        symbolic.
        """
        return format_expression(fold_constants(parse(line)))

    def _execute(self, statement: Statement, line: str) -> float:
        """Evaluate a statement, apply any assignment, store the result as ans and record the line
        in the history.
        """
        expression = statement.expression if isinstance(statement, Assignment) else statement
        value = evaluate_node(expression, self._environment)
        if isinstance(statement, Assignment):
            self._environment.assign(statement.name, value)
        self._environment.assign("ans", value)
        self._history.append(HistoryEntry(line, value))
        return value
