"""Lexical analysis of arithmetic expressions."""

from dataclasses import dataclass
from enum import Enum

from calc.errors import CalculatorError


class TokenKind(Enum):
    """Categories of token produced by lexical analysis."""

    NUMBER = "number"
    IDENTIFIER = "identifier"
    OPERATOR = "operator"
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    COMMA = ","
    EQUALS = "="
    END = "end"


@dataclass(frozen=True)
class Token:
    """A token with its kind, source text and zero-based starting position."""

    kind: TokenKind
    text: str
    position: int


OPERATORS = frozenset("+-*/%^")
PUNCTUATION = frozenset("(),=")


def tokenize(source: str) -> list[Token]:
    """Split source into unsigned decimal numbers, identifiers, operators and punctuation ending
    with one end token, skipping whitespace and rejecting malformed input.
    """
    tokens: list[Token] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char.isspace():
            index += 1
        elif char.isdigit() or char == ".":
            start = index
            while index < len(source) and (source[index].isdigit() or source[index] == "."):
                index += 1
            text = source[start:index]
            if text == "." or text.count(".") > 1:
                raise CalculatorError(f"Invalid number {text!r}", start)
            tokens.append(Token(TokenKind.NUMBER, text, start))
        elif char.isalpha() or char == "_":
            start = index
            while index < len(source) and (source[index].isalnum() or source[index] == "_"):
                index += 1
            tokens.append(Token(TokenKind.IDENTIFIER, source[start:index], start))
        elif char in OPERATORS:
            tokens.append(Token(TokenKind.OPERATOR, char, index))
            index += 1
        elif char in PUNCTUATION:
            tokens.append(Token(TokenKind(char), char, index))
            index += 1
        else:
            raise CalculatorError(f"Unexpected character {char!r}", index)
    tokens.append(Token(TokenKind.END, "", len(source)))
    return tokens
