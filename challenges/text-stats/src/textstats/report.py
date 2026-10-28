"""Summary reports combining the individual text statistics."""

from dataclasses import asdict, dataclass
from typing import Any

from textstats.analysis import (
    average_sentence_length,
    average_word_length,
    lexical_diversity,
    most_common,
    reading_time_minutes,
    sentence_count,
    unique_word_count,
    word_count,
)
from textstats.readability import flesch_reading_ease, reading_ease_label
from textstats.stopwords import ENGLISH_STOPWORDS, keywords


@dataclass(frozen=True)
class TextReport:
    """Immutable summary of counts, averages, diversity, reading time, reading ease, top frequency
    pairs and keyword pairs excluding stop-word entries for one text."""

    words: int
    unique_words: int
    sentences: int
    average_word_length: float
    average_sentence_length: float
    lexical_diversity: float
    reading_minutes: int
    reading_ease: float
    top_words: list[tuple[str, int]]
    keywords: list[tuple[str, int]]

    def to_dict(self) -> dict[str, Any]:
        """Return the report as a JSON-serialisable dictionary with each frequency pair converted to
        an object holding word and count keys."""
        data = asdict(self)
        for field in ("top_words", "keywords"):
            data[field] = [{"word": word, "count": total} for word, total in data[field]]
        return data


def build_report(
    text: str,
    top: int = 5,
    words_per_minute: int = 200,
    stopwords: frozenset[str] = ENGLISH_STOPWORDS,
) -> TextReport:
    """Return a report for the text using the given top count, reading pace and stop-word set,
    raising ValueError when top is negative."""
    if top < 0:
        raise ValueError("top must not be negative")
    return TextReport(
        words=word_count(text),
        unique_words=unique_word_count(text),
        sentences=sentence_count(text),
        average_word_length=average_word_length(text),
        average_sentence_length=average_sentence_length(text),
        lexical_diversity=lexical_diversity(text),
        reading_minutes=reading_time_minutes(text, words_per_minute),
        reading_ease=flesch_reading_ease(text),
        top_words=most_common(text, top),
        keywords=keywords(text, top, stopwords),
    )


def format_minutes(minutes: int) -> str:
    """Return the minute count followed by a unit that is singular for exactly one and plural
    otherwise."""
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit}"


def format_frequencies(pairs: list[tuple[str, int]]) -> str:
    """Return frequency pairs as comma-separated entries with each count in parentheses, or none
    when there are no pairs."""
    if not pairs:
        return "none"
    return ", ".join(f"{word} ({total})" for word, total in pairs)


def format_report(report: TextReport) -> str:
    """Return the report as label and value lines with labels padded to a common width and no
    trailing newline."""
    rows = [
        ("Words", str(report.words)),
        ("Unique words", str(report.unique_words)),
        ("Sentences", str(report.sentences)),
        ("Average word length", f"{report.average_word_length:.2f}"),
        ("Average sentence length", f"{report.average_sentence_length:.2f}"),
        ("Lexical diversity", f"{report.lexical_diversity:.2f}"),
        ("Reading time", format_minutes(report.reading_minutes)),
        (
            "Reading ease",
            f"{report.reading_ease:.2f} ({reading_ease_label(report.reading_ease)})",
        ),
        ("Top words", format_frequencies(report.top_words)),
        ("Keywords", format_frequencies(report.keywords)),
    ]
    width = max(len(label) for label, _ in rows) + 1
    return "\n".join(f"{label + ':':<{width}} {value}" for label, value in rows)
