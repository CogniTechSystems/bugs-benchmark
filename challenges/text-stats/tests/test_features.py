import io
import json

import pytest
from textstats import (
    average_sentence_length,
    build_report,
    content_words,
    count_syllables,
    flesch_kincaid_grade,
    flesch_reading_ease,
    format_report,
    keywords,
    lexical_diversity,
    load_stopwords,
    most_common_ngrams,
    ngram_frequencies,
    ngrams,
    normalize,
    reading_ease_label,
    sentences,
    speaking_time_minutes,
    syllable_count,
    unique_word_count,
    word_count,
)
from textstats.cli import main
from textstats.normalize import collapse_whitespace, normalize_quotes, unwrap_hyphenation
from textstats.report import format_frequencies, format_minutes
from textstats.stopwords import parse_stopwords, remove_stopwords

SAMPLE = "the cat saw the dog. the dog ran."


def test_word_and_unique_counts():
    assert word_count(SAMPLE) == 8
    assert unique_word_count(SAMPLE) == 5


def test_lexical_diversity():
    assert lexical_diversity("a b a b") == 0.5
    assert lexical_diversity("") == 0.0


def test_sentences_are_stripped_and_split_on_runs():
    assert sentences(" one.  two?! three ") == ["one", "two", "three"]


def test_average_sentence_length():
    assert average_sentence_length(SAMPLE) == 4.0
    assert average_sentence_length("") == 0.0


def test_speaking_time_uses_speaking_pace():
    assert speaking_time_minutes(" ".join(["word"] * 260)) == 2
    assert speaking_time_minutes("") == 0


def test_normalize_quotes():
    assert normalize_quotes("“don’t”") == '"don\'t"'


def test_unwrap_hyphenation_joins_broken_words_only():
    assert unwrap_hyphenation("exam-\n  ple") == "example"
    assert unwrap_hyphenation("well-known") == "well-known"


def test_collapse_whitespace():
    assert collapse_whitespace("  a \t b\n\nc  ") == "a b c"


def test_normalize_combines_steps_and_keeps_case():
    assert normalize("It’s  a  co-\noperative") == "It's a cooperative"


def test_parse_stopwords_lowercases_and_skips_blank_lines():
    assert parse_stopwords(["  The ", "", "AND", "  "]) == frozenset({"the", "and"})


def test_load_stopwords(tmp_path):
    path = tmp_path / "stop.txt"
    path.write_text("cat\nDog\n", encoding="utf-8")
    assert load_stopwords(path) == frozenset({"cat", "dog"})


def test_remove_stopwords_preserves_order():
    assert remove_stopwords(["the", "cat", "and", "dog"]) == ["cat", "dog"]


def test_content_words():
    assert content_words(SAMPLE) == ["cat", "saw", "dog", "dog", "ran"]
    assert content_words("a cat", frozenset({"cat"})) == ["a"]


def test_keywords_rank_content_words():
    assert keywords(SAMPLE, 1) == [("dog", 2)]


def test_keywords_break_ties_alphabetically():
    assert keywords("pear apple pear apple fig", 3) == [("apple", 2), ("pear", 2), ("fig", 1)]


def test_ngrams():
    assert ngrams(["a", "b", "c"], 2) == [("a", "b"), ("b", "c")]
    assert ngrams(["a"], 2) == []


def test_ngrams_reject_invalid_size():
    with pytest.raises(ValueError):
        ngrams(["a"], 0)


def test_ngram_frequencies():
    assert ngram_frequencies("to be or not to be", 2)[("to", "be")] == 2


def test_most_common_ngrams_orders_by_count_then_phrase():
    assert most_common_ngrams("to be or not to be", 2, 3) == [
        ("to be", 2),
        ("be or", 1),
        ("not to", 1),
    ]


@pytest.mark.parametrize(
    ("word", "expected"),
    [("cat", 1), ("make", 1), ("table", 2), ("agree", 2), ("syllable", 3), ("Banana", 3)],
)
def test_count_syllables(word, expected):
    assert count_syllables(word) == expected


def test_count_syllables_of_non_words():
    assert count_syllables("'") == 0
    assert count_syllables("rhythm") == 1


def test_syllable_count():
    assert syllable_count("the table") == 3


def test_flesch_scores():
    text = "the cat sat on the mat."
    assert flesch_reading_ease(text) == pytest.approx(116.145, abs=0.01)
    assert flesch_kincaid_grade(text) == pytest.approx(-1.45, abs=0.01)


def test_flesch_scores_of_empty_text():
    assert flesch_reading_ease("") == 0.0
    assert flesch_kincaid_grade("") == 0.0


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (95.0, "easy"),
        (80.0, "easy"),
        (65.0, "standard"),
        (30.0, "difficult"),
        (10.0, "very difficult"),
    ],
)
def test_reading_ease_label(score, label):
    assert reading_ease_label(score) == label


def test_build_report():
    report = build_report(SAMPLE, top=2, words_per_minute=4)
    assert report.words == 8
    assert report.unique_words == 5
    assert report.sentences == 2
    assert report.average_sentence_length == 4.0
    assert report.reading_minutes == 2
    assert report.top_words == [("the", 3), ("dog", 2)]
    assert report.keywords[0] == ("dog", 2)


def test_build_report_rejects_negative_top():
    with pytest.raises(ValueError):
        build_report(SAMPLE, top=-1)


def test_build_report_rejects_invalid_speed():
    with pytest.raises(ValueError):
        build_report(SAMPLE, words_per_minute=0)


def test_report_to_dict():
    data = build_report(SAMPLE, top=1).to_dict()
    assert data["top_words"] == [{"word": "the", "count": 3}]
    assert data["keywords"] == [{"word": "dog", "count": 2}]
    assert data["words"] == 8


def test_format_helpers():
    assert format_minutes(1) == "1 minute"
    assert format_minutes(0) == "0 minutes"
    assert format_minutes(3) == "3 minutes"
    assert format_frequencies([]) == "none"
    assert format_frequencies([("a", 2), ("b", 1)]) == "a (2), b (1)"


def test_format_report():
    lines = format_report(build_report(SAMPLE, top=1, words_per_minute=8)).splitlines()
    assert lines[0] == "Words:                   8"
    assert "Reading time:            1 minute" in lines
    assert lines[-2] == "Top words:               the (3)"
    assert lines[-1] == "Keywords:                dog (2)"


def test_cli_prints_text_report(tmp_path, capsys):
    path = tmp_path / "sample.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    assert main([str(path), "--top", "1", "--wpm", "8"]) == 0
    output = capsys.readouterr().out
    assert "Reading time:            1 minute" in output
    assert "Top words:               the (3)" in output


def test_cli_prints_json(tmp_path, capsys):
    path = tmp_path / "sample.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    assert main([str(path), "--json", "--top", "1"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["sentences"] == 2
    assert data["top_words"] == [{"word": "the", "count": 3}]


def test_cli_uses_custom_stopwords(tmp_path, capsys):
    text_path = tmp_path / "sample.txt"
    text_path.write_text(SAMPLE, encoding="utf-8")
    stop_path = tmp_path / "stop.txt"
    stop_path.write_text("dog\n", encoding="utf-8")
    assert main([str(text_path), "--json", "--top", "1", "--stopwords", str(stop_path)]) == 0
    assert json.loads(capsys.readouterr().out)["keywords"] == [{"word": "the", "count": 3}]


def test_cli_reads_standard_input(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(SAMPLE))
    assert main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["words"] == 8


def test_cli_reports_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "missing.txt")]) == 1
    assert capsys.readouterr().err.startswith("textstats: ")


def test_cli_rejects_invalid_speed():
    with pytest.raises(SystemExit):
        main(["--wpm", "0"])
