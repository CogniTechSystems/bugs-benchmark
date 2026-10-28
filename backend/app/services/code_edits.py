"""Locating and applying search-and-replace code changes."""

import textwrap
from dataclasses import dataclass


class ChangeNotApplicableError(ValueError):
    """Raised when the original code of a change cannot be located."""


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    line: int
    indent: str | None
    newline: str


def apply_change(
    content: str, original: str, replacement: str, near_line: int | None = None
) -> str:
    """Replace ``original`` with ``replacement`` in ``content``.

    An exact match is attempted first. If none exists, lines are compared with surrounding
    whitespace ignored and the replacement is re-indented to match the located block. When the
    original occurs more than once, the occurrence closest to ``near_line`` is replaced.
    """
    match = _find(content, original, near_line)
    if match.indent is None:
        new_text = replacement
    else:
        new_text = _reindent(replacement, match.indent, match.newline)
        if not content[: match.end].endswith(("\n", "\r")):
            new_text = new_text.rstrip("\r\n")
    return content[: match.start] + new_text + content[match.end :]


def locate_change(content: str, original: str, near_line: int | None = None) -> int:
    """Return the 1-based line on which ``original`` starts."""
    return _find(content, original, near_line).line


def _find(content: str, original: str, near_line: int | None) -> _Match:
    if not original.strip():
        raise ChangeNotApplicableError("The original code is empty.")

    exact = _exact_matches(content, original)
    candidates = exact or _whitespace_insensitive_matches(content, original)
    if not candidates:
        raise ChangeNotApplicableError("The original code was not found in the file.")
    if near_line is None:
        return candidates[0]
    return min(candidates, key=lambda match: abs(match.line - near_line))


def _exact_matches(content: str, original: str) -> list[_Match]:
    matches = []
    index = content.find(original)
    while index != -1:
        line = content.count("\n", 0, index) + 1
        matches.append(_Match(index, index + len(original), line, None, "\n"))
        index = content.find(original, index + 1)
    return matches


def _whitespace_insensitive_matches(content: str, original: str) -> list[_Match]:
    lines = content.splitlines(keepends=True)
    target = [line.strip() for line in original.strip("\r\n").splitlines()]
    size = len(target)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    matches = []
    for start in range(len(lines) - size + 1):
        block = lines[start : start + size]
        if [line.strip() for line in block] != target:
            continue
        first = block[0]
        indent = first[: len(first) - len(first.lstrip())]
        newline = "\r\n" if block[-1].endswith("\r\n") else "\n"
        matches.append(_Match(offsets[start], offsets[start + size], start + 1, indent, newline))
    return matches


def _reindent(code: str, indent: str, newline: str) -> str:
    block = textwrap.dedent(code.strip("\r\n"))
    return "".join((indent + line if line.strip() else "") + newline for line in block.splitlines())
