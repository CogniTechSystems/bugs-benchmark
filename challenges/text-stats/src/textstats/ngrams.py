"""Sequences of adjacent word tokens and their frequencies."""

from collections import Counter
from collections.abc import Sequence

from textstats.analysis import words


def ngrams(tokens: Sequence[str], size: int) -> list[tuple[str, ...]]:
    """Return every run of adjacent tokens of the given size in order, empty when too short, raising
    ValueError when the size is below one."""
    if size < 1:
        raise ValueError("size must be positive")
    return [tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)]


def ngram_frequencies(text: str, size: int) -> Counter[tuple[str, ...]]:
    """Return a counter of every n-gram of the given size over the lower-cased word tokens of the
    text, spanning sentence boundaries."""
    return Counter(ngrams(words(text), size))


def most_common_ngrams(text: str, size: int, count: int) -> list[tuple[str, int]]:
    """Return up to the requested number of space-joined phrase and frequency pairs, ordered by
    descending frequency with ties broken in ascending alphabetical order."""
    phrases = Counter(
        {" ".join(gram): total for gram, total in ngram_frequencies(text, size).items()}
    )
    ranked = sorted(phrases.items(), key=lambda pair: (-pair[1], pair[0]))
    return ranked[:count]
