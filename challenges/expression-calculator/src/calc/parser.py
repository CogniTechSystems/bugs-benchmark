"""Recursive descent parser turning calculator source text into syntax trees."""

from dataclasses import dataclass, field

from calc.errors import CalculatorError
from calc.nodes import BinaryOp, Call, Negate, Node, Number, Variable
from calc.tokens import Token, TokenKind, tokenize


@dataclass(frozen=True)
class Assignment:
    """A statement binding a variable name to the value of an expression."""

    name: str
    expression: Node
    position: int = field(default=0, compare=False)


Statement = Assignment | Node


def parse(source: str) -> Node:
    """Parse source text as one complete expression, raising an error positioned at the offending
    token for lexical, syntax or trailing input faults.
    """
    return _Parser(tokenize(source)).parse_expression()


def parse_statement(source: str) -> Statement:
    """Parse source text as a variable assignment or a bare expression, raising a positioned error
    for lexical, syntax or trailing input faults.
    """
    return _Parser(tokenize(source)).parse_statement()


class _Parser:
    """Cursor over a token list with one method per grammar rule."""

    def __init__(self, tokens: list[Token]) -> None:
        """Start the cursor at the first token of a list that ends with an end token."""
        self._tokens = tokens
        self._index = 0

    def parse_expression(self) -> Node:
        """Parse a complete expression and raise an error unless all input is consumed."""
        node = self._expression()
        self._expect_end()
        return node

    def parse_statement(self) -> Statement:
        """Parse an assignment when an identifier precedes an equals sign, otherwise an expression,
        and require all input consumed.
        """
        statement: Statement
        if self._current.kind is TokenKind.IDENTIFIER and self._next.kind is TokenKind.EQUALS:
            name = self._advance()
            self._advance()
            statement = Assignment(name.text, self._expression(), name.position)
        else:
            statement = self._expression()
        self._expect_end()
        return statement

    @property
    def _current(self) -> Token:
        """Return the token at the cursor."""
        return self._tokens[self._index]

    @property
    def _next(self) -> Token:
        """Return the token after the cursor, or the end token when none follows."""
        return self._tokens[min(self._index + 1, len(self._tokens) - 1)]

    def _advance(self) -> Token:
        """Return the current token and move past it, never moving beyond the end token."""
        token = self._current
        if token.kind is not TokenKind.END:
            self._index += 1
        return token

    def _at_operator(self, *symbols: str) -> bool:
        """Return whether the current token is an operator with one of the given symbols."""
        return self._current.kind is TokenKind.OPERATOR and self._current.text in symbols

    def _expect_end(self) -> None:
        """Raise an error positioned at the current token unless all tokens are consumed."""
        if self._current.kind is not TokenKind.END:
            raise CalculatorError(f"Unexpected {self._current.text!r}", self._current.position)

    def _expect_closing(self, opening: Token) -> None:
        """Consume a right parenthesis or raise an error positioned at the opening parenthesis."""
        if self._advance().kind is not TokenKind.RIGHT_PAREN:
            raise CalculatorError("Unclosed parenthesis", opening.position)

    def _expression(self) -> Node:
        """Parse a chain of terms joined by addition and subtraction, grouping the operators left-
        associatively.
        """
        value = self._term()
        while self._at_operator("+", "-"):
            operator = self._advance()
            value = BinaryOp(operator.text, value, self._term(), operator.position)
        return value

    def _term(self) -> Node:
        """Parse a chain of unary operands joined by multiplication, division and remainder,
        grouping the operators left-associatively.
        """
        value = self._unary()
        while self._at_operator("*", "/", "%"):
            operator = self._advance()
            right = self._term()
            value = BinaryOp(operator.text, value, right, operator.position)
        return value

    def _unary(self) -> Node:
        """Parse prefix negations, which bind tighter than multiplicative operators and looser than
        exponentiation, before a power.
        """
        if self._at_operator("-"):
            operator = self._advance()
            return Negate(self._unary(), operator.position)
        return self._power()

    def _power(self) -> Node:
        """Parse a primary with optional exponentiation, grouping right-associatively and allowing a
        negated exponent.
        """
        value = self._primary()
        while self._at_operator("^"):
            operator = self._advance()
            value = BinaryOp("^", value, self._primary(), operator.position)
        return value

    def _primary(self) -> Node:
        """Parse a number, variable, function call or parenthesised expression, raising an error for
        any other token.
        """
        token = self._advance()
        if token.kind is TokenKind.NUMBER:
            return Number(float(token.text), token.position)
        if token.kind is TokenKind.IDENTIFIER:
            if self._current.kind is TokenKind.LEFT_PAREN:
                return self._call(token)
            return Variable(token.text, token.position)
        if token.kind is TokenKind.LEFT_PAREN:
            node = self._expression()
            self._expect_closing(token)
            return node
        if token.kind is TokenKind.END:
            raise CalculatorError("Unexpected end of expression", token.position)
        raise CalculatorError(f"Unexpected {token.text!r}", token.position)

    def _call(self, name: Token) -> Call:
        """Parse the parenthesised, comma-separated argument expressions of a function call."""
        opening = self._advance()
        arguments: list[Node] = []
        if self._current.kind is not TokenKind.RIGHT_PAREN:
            arguments.append(self._expression())
            while self._current.kind is TokenKind.COMMA:
                self._advance()
                arguments.append(self._expression())
        self._expect_closing(opening)
        return Call(name.text, tuple(arguments), name.position)
