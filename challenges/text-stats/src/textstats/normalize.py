"""Clean-up of raw text before it is analysed."""

import re

QUOTE_TRANSLATION = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
    }
)
LINE_BREAK_HYPHENATION = re.compile(r"(?<=[A-Za-z])-\s*\n\s*(?=[A-Za-z])")
WHITESPACE = re.compile(r"\s+")


def normalize_quotes(text: str) -> str:
    """Return the text with typographic single and double quotes replaced by their ASCII
    equivalents, leaving every other character unchanged."""
    return text.translate(QUOTE_TRANSLATION)


def unwrap_hyphenation(text: str) -> str:
    """Return the text with each hyphen between letters that precedes a line break removed along
    with the break and surrounding whitespace."""
    return LINE_BREAK_HYPHENATION.sub("", text)


def collapse_whitespace(text: str) -> str:
    """Return the text with every run of whitespace replaced by a single space and both ends
    trimmed."""
    return WHITESPACE.sub(" ", text).strip()


def normalize(text: str) -> str:
    """Return the text with quotes standardised, line-break hyphenation removed and whitespace
    collapsed, in that order, preserving letter case."""
    return collapse_whitespace(unwrap_hyphenation(normalize_quotes(text)))
