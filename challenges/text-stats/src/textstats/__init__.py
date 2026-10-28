"""Word frequency, sentence, readability and reading-time statistics for English text."""

from textstats.analysis import (
    average_sentence_length,
    average_word_length,
    lexical_diversity,
    most_common,
    reading_time_minutes,
    sentence_count,
    sentences,
    speaking_time_minutes,
    unique_word_count,
    word_count,
    word_frequencies,
    words,
)
from textstats.ngrams import most_common_ngrams, ngram_frequencies, ngrams
from textstats.normalize import normalize
from textstats.readability import (
    count_syllables,
    flesch_kincaid_grade,
    flesch_reading_ease,
    reading_ease_label,
    syllable_count,
)
from textstats.report import TextReport, build_report, format_report
from textstats.stopwords import ENGLISH_STOPWORDS, content_words, keywords, load_stopwords

__all__ = [
    "ENGLISH_STOPWORDS",
    "TextReport",
    "average_sentence_length",
    "average_word_length",
    "build_report",
    "content_words",
    "count_syllables",
    "flesch_kincaid_grade",
    "flesch_reading_ease",
    "format_report",
    "keywords",
    "lexical_diversity",
    "load_stopwords",
    "most_common",
    "most_common_ngrams",
    "ngram_frequencies",
    "ngrams",
    "normalize",
    "reading_ease_label",
    "reading_time_minutes",
    "sentence_count",
    "sentences",
    "speaking_time_minutes",
    "syllable_count",
    "unique_word_count",
    "word_count",
    "word_frequencies",
    "words",
]
