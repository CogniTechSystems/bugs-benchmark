import pytest

from app.services.code_edits import ChangeNotApplicableError, apply_change, locate_change

SOURCE = """def total(items):
    result = 0
    for item in items:
        result += item
    return result
"""


def test_exact_replacement():
    patched = apply_change(SOURCE, "    result = 0\n", "    result = 1\n")
    assert "result = 1" in patched
    assert patched.count("\n") == SOURCE.count("\n")


def test_whitespace_insensitive_replacement_is_reindented():
    patched = apply_change(
        SOURCE, "for item in items:\nresult += item", "for item in items:\n    result -= item"
    )
    assert "    for item in items:\n        result -= item\n" in patched


def test_closest_occurrence_to_line_is_replaced():
    content = "x = 1\ny = 2\nx = 1\n"
    assert apply_change(content, "x = 1", "x = 3", near_line=3) == "x = 1\ny = 2\nx = 3\n"
    assert locate_change(content, "x = 1", near_line=3) == 3


def test_missing_original_raises():
    with pytest.raises(ChangeNotApplicableError):
        apply_change(SOURCE, "not present", "anything")


def test_empty_original_raises():
    with pytest.raises(ChangeNotApplicableError):
        locate_change(SOURCE, "   ")
