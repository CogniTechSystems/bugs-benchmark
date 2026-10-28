"""Readability scores based on word, sentence and syllable counts."""

import re

from textstats.analysis import sentence_count, words

VOWEL_GROUP = re.compile(r"[aeiouy]+")
READING_EASE_BANDS = (
    (80.0, "easy"),
    (60.0, "standard"),
    (30.0, "difficult"),
)


def count_syllables(word: str) -> int:
    """Count vowel groups, y included, in one word, ignoring case and a silent final e not after l
    or e, with at least one if any letter exists."""
    letters = word.lower().strip("'")
    if not any(character.isalpha() for character in letters):
        return 0
    syllables = len(VOWEL_GROUP.findall(letters))
    if letters.endswith("e") and not letters.endswith(("le", "ee")) and syllables > 1:
        syllables -= 1
    return max(syllables, 1)


def syllable_count(text: str) -> int:
    """Return the estimated total syllable count over every word token of the text."""
    return sum(count_syllables(word) for word in words(text))


def _ratios(text: str) -> tuple[float, float] | None:
    """Return the word-per-sentence and syllable-per-word ratios, counting at least one sentence, or
    None for text without any word tokens."""
    found = words(text)
    if not found:
        return None
    words_per_sentence = len(found) / max(sentence_count(text), 1)
    syllables_per_word = sum(count_syllables(word) for word in found) / len(found)
    return words_per_sentence, syllables_per_word


def flesch_reading_ease(text: str) -> float:
    """Return the Flesch reading-ease score rounded to two decimal places, treating unterminated
    text as one sentence, or zero for text without any word tokens."""
    ratios = _ratios(text)
    if ratios is None:
        return 0.0
    words_per_sentence, syllables_per_word = ratios
    return round(206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word, 2)


def flesch_kincaid_grade(text: str) -> float:
    """Return the Flesch-Kincaid grade level rounded to two decimal places, treating unterminated
    text as one sentence, or zero for text without any word tokens."""
    ratios = _ratios(text)
    if ratios is None:
        return 0.0
    words_per_sentence, syllables_per_word = ratios
    return round(0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59, 2)


def reading_ease_label(score: float) -> str:
    """Return the difficulty label for a reading-ease score, choosing the first band whose threshold
    the score meets or exceeds, else very difficult."""
    for threshold, label in READING_EASE_BANDS:
        if score >= threshold:
            return label
    return "very difficult"
