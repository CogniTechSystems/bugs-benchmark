import pytest
from textstats import (
    average_word_length,
    most_common,
    reading_time_minutes,
    sentence_count,
    word_frequencies,
    words,
)


def test_words_are_lowercased():
    assert words("The Cat sat") == ["the", "cat", "sat"]


def test_word_frequencies_ignore_case():
    assert word_frequencies("Go go GO")["go"] == 3


def test_words_keep_apostrophes():
    assert words("don't stop") == ["don't", "stop"]


def test_words_split_on_punctuation_and_digits():
    assert words("one,two 3 four") == ["one", "two", "four"]


def test_most_common_orders_by_count():
    assert most_common("b a b c b a", 2) == [("b", 3), ("a", 2)]


def test_most_common_breaks_ties_alphabetically():
    assert most_common("pear apple pear apple fig", 3) == [
        ("apple", 2),
        ("pear", 2),
        ("fig", 1),
    ]


def test_average_word_length():
    assert average_word_length("ab abcd") == 3.0


def test_average_word_length_of_empty_text():
    assert average_word_length("") == 0.0


def test_sentence_count():
    assert sentence_count("one. two! three?") == 3


def test_sentence_count_collapses_repeated_punctuation():
    assert sentence_count("wait... what") == 2


def test_reading_time_for_whole_minutes():
    assert reading_time_minutes(" ".join(["word"] * 400)) == 2


def test_reading_time_of_empty_text_is_zero():
    assert reading_time_minutes("") == 0


def test_reading_time_rounds_up_partial_minutes():
    assert reading_time_minutes(" ".join(["word"] * 201)) == 2
    assert reading_time_minutes("word") == 1


def test_reading_time_rejects_invalid_speed():
    with pytest.raises(ValueError):
        reading_time_minutes("word", words_per_minute=0)
