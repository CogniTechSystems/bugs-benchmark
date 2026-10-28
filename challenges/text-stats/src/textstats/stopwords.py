"""Stop-word handling and keyword extraction."""

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from textstats.analysis import words

STOPWORD_LIST = (
    "a an and are as at be but by for from had has have he her his i in is it its of "
    "on or she that the their they this to was we were with you"
)
ENGLISH_STOPWORDS = frozenset(STOPWORD_LIST.split())


def parse_stopwords(lines: Iterable[str]) -> frozenset[str]:
    """Return a frozen set of the stripped, lower-cased entries of the given lines, ignoring blank
    lines."""
    return frozenset(line.strip().lower() for line in lines if line.strip())


def load_stopwords(path: Path) -> frozenset[str]:
    """Return the stop-word set parsed from a UTF-8 file holding one entry per line."""
    return parse_stopwords(path.read_text(encoding="utf-8").splitlines())


def remove_stopwords(
    tokens: Iterable[str], stopwords: frozenset[str] = ENGLISH_STOPWORDS
) -> list[str]:
    """Return the tokens not present in the stop-word set, preserving order and comparing exactly
    without case folding."""
    return [token for token in tokens if token not in stopwords]


def content_words(text: str, stopwords: frozenset[str] = ENGLISH_STOPWORDS) -> list[str]:
    """Return the lower-cased word tokens of the text that are not in the stop-word set, in order of
    appearance."""
    return remove_stopwords(words(text), stopwords)


def keywords(
    text: str, count: int, stopwords: frozenset[str] = ENGLISH_STOPWORDS
) -> list[tuple[str, int]]:
    """Return up to the requested number of frequency pairs for tokens outside the stop-word set,
    ordered by descending frequency with ties broken alphabetically."""
    frequencies = Counter(content_words(text, stopwords))
    ranked = sorted(frequencies.items(), key=lambda pair: (-pair[1], pair[0]))
    return ranked[:count]
