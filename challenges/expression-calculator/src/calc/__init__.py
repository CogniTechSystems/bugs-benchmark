"""A small arithmetic expression language with variables, functions, constant folding and
interactive sessions.
"""

from calc.environment import Environment
from calc.errors import CalculatorError, render_error
from calc.evaluator import evaluate, evaluate_node
from calc.folding import fold_constants
from calc.formatter import format_expression
from calc.parser import parse, parse_statement
from calc.session import Session

__all__ = [
    "CalculatorError",
    "Environment",
    "Session",
    "evaluate",
    "evaluate_node",
    "fold_constants",
    "format_expression",
    "parse",
    "parse_statement",
    "render_error",
]
