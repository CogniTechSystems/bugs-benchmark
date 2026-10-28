"""Command-line interface printing a statistics report for a text file."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from textstats.normalize import normalize
from textstats.report import build_report, format_report
from textstats.stopwords import ENGLISH_STOPWORDS, load_stopwords


def positive_int(value: str) -> int:
    """Parse a command-line value as an integer, raising an argparse type error when it is not a
    whole number or is below one."""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from error
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value!r} must be at least 1")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the command, accepting an input path, top count, reading pace,
    stop-word file and JSON flag."""
    parser = argparse.ArgumentParser(
        prog="textstats", description="Print statistics for English text."
    )
    parser.add_argument(
        "path", nargs="?", default="-", help="text file to analyse, or '-' for standard input"
    )
    parser.add_argument("--top", type=positive_int, default=5, help="number of top words")
    parser.add_argument(
        "--wpm", type=positive_int, default=200, help="reading speed in words per minute"
    )
    parser.add_argument("--stopwords", type=Path, help="file of stop words, one per line")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser


def read_text(path: str) -> str:
    """Return the UTF-8 contents of the given path, reading standard input instead when the path is
    a single dash."""
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command on normalised input, print a text or JSON report, and return zero on success
    or one when a file cannot be read."""
    arguments = build_parser().parse_args(argv)
    try:
        text = read_text(arguments.path)
        stopwords = (
            load_stopwords(arguments.stopwords) if arguments.stopwords else ENGLISH_STOPWORDS
        )
    except OSError as error:
        print(f"textstats: {error}", file=sys.stderr)
        return 1
    report = build_report(normalize(text), arguments.top, arguments.wpm, stopwords)
    if arguments.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report(report))
    return 0
