"""Word and sentence statistics for plain English text."""

import re
from collections import Counter

WORD_PATTERN = re.compile(r"[a-z']+")
SENTENCE_BOUNDARY = re.compile(r"[.!?]+")
SPEAKING_WORDS_PER_MINUTE = 130


def words(text: str) -> list[str]:
    """Return the lower-cased runs of letters and apostrophes in the text, in order of appearance,
    treating all other characters as separators."""
    return WORD_PATTERN.findall(text)


def word_count(text: str) -> int:
    """Return the number of word tokens in the text, counting every occurrence including repeats."""
    return len(words(text))


def unique_word_count(text: str) -> int:
    """Return the number of distinct word tokens in the text, ignoring letter case."""
    return len(set(words(text)))


def lexical_diversity(text: str) -> float:
    """Return the ratio of distinct to total word tokens rounded to two decimal places, or zero for
    text without any word tokens."""
    total = word_count(text)
    if total == 0:
        return 0.0
    return round(unique_word_count(text) / total, 2)


def word_frequencies(text: str) -> Counter[str]:
    """Return a counter mapping each lower-cased word token in the text to the number of times it
    occurs."""
    return Counter(words(text))


def most_common(text: str, count: int) -> list[tuple[str, int]]:
    """Return up to the requested number of word and frequency pairs, ordered by descending
    frequency with ties broken in ascending alphabetical order."""
    frequencies = word_frequencies(text)
    ranked = sorted(frequencies.items(), key=lambda pair: (pair[1], pair[0]), reverse=True)
    return ranked[:count]


def average_word_length(text: str) -> float:
    """Return the mean character length of word tokens, apostrophes included, rounded to two decimal
    places, or zero for text without any word tokens."""
    found = words(text)
    if not found:
        return 0.0
    return round(sum(len(word) for word in found) / len(found), 2)


def sentences(text: str) -> list[str]:
    """Return the stripped non-empty segments of the text between runs of full stops, exclamation
    marks or question marks, excluding the terminating punctuation."""
    return [part.strip() for part in SENTENCE_BOUNDARY.split(text) if part.strip()]


def sentence_count(text: str) -> int:
    """Return the number of non-empty segments of the text separated by runs of full stops,
    exclamation marks or question marks."""
    return sum(1 for sentence in SENTENCE_BOUNDARY.split(text) if sentence.strip())


def average_sentence_length(text: str) -> float:
    """Return the mean number of word tokens per sentence rounded to two decimal places, or zero for
    text without any sentences."""
    total = sentence_count(text)
    if total == 0:
        return 0.0
    return round(word_count(text) / total, 2)


def reading_time_minutes(text: str, words_per_minute: int = 200) -> int:
    """Return the reading time in whole minutes at the given pace, rounding any partial minute up,
    and raise ValueError when the pace is below one."""
    if words_per_minute < 1:
        raise ValueError("words_per_minute must be positive")
    return len(words(text)) // words_per_minute


def speaking_time_minutes(text: str) -> int:
    """Return the time in whole minutes to read the text aloud at a typical speaking pace, rounding
    any partial minute up."""
    return reading_time_minutes(text, words_per_minute=SPEAKING_WORDS_PER_MINUTE)
