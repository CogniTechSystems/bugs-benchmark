"""Integrity checks for every challenge in the catalogue.

For each challenge the hidden tests must fail on the shipped code only where a bug is
expected, each reference fix must repair its bug without regressions, and the source given to
the agent must not contain comments that could hint at the defects.
"""

import io
import tokenize

import pytest

from app.config import Settings
from app.services.challenges import Challenge, ChallengeCatalog
from app.services.code_edits import apply_change
from app.services.test_runner import TestRunner, expand_test_ids

CATALOG = ChallengeCatalog(Settings().challenges_dir)
RUNNER = TestRunner(timeout_seconds=120)


def _source(challenge: Challenge, relative_path: str) -> str:
    return (challenge.source_dir / relative_path).read_text(encoding="utf-8")


def test_catalog_covers_every_difficulty():
    assert {challenge.difficulty for challenge in CATALOG.all()} == {"easy", "medium", "hard"}


@pytest.mark.parametrize("challenge", CATALOG.all(), ids=lambda challenge: challenge.slug)
def test_reference_fixes_repair_each_bug_independently(challenge: Challenge):
    baseline = RUNNER.run(challenge)
    bug_tests = {bug.key: expand_test_ids(bug.tests, baseline.all_tests) for bug in challenge.bugs}
    regression_tests = baseline.all_tests.difference(*bug_tests.values())

    assert all(bug_tests.values()), "Every bug must reference at least one existing test."
    assert regression_tests <= baseline.passed, "Unrelated tests must pass on the shipped code."

    for bug in challenge.bugs:
        assert bug_tests[bug.key] & baseline.failed, f"{bug.key} is not detected by its tests."
        patched = apply_change(_source(challenge, bug.file), bug.original, bug.replacement)
        result = RUNNER.run(challenge, {bug.file: patched})
        assert bug_tests[bug.key] | regression_tests <= result.passed, bug.key


@pytest.mark.parametrize("challenge", CATALOG.all(), ids=lambda challenge: challenge.slug)
def test_all_reference_fixes_together_pass_the_suite(challenge: Challenge):
    overrides: dict[str, str] = {}
    for bug in challenge.bugs:
        content = overrides.get(bug.file) or _source(challenge, bug.file)
        overrides[bug.file] = apply_change(content, bug.original, bug.replacement)
    result = RUNNER.run(challenge, overrides)
    assert result.failed == frozenset(), result.output
    assert result.passed


@pytest.mark.parametrize("challenge", CATALOG.all(), ids=lambda challenge: challenge.slug)
def test_sources_contain_no_comments(challenge: Challenge):
    for relative_path in challenge.source_files():
        source = _source(challenge, relative_path)
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        comments = [token.string for token in tokens if token.type == tokenize.COMMENT]
        allowed = [comment for comment in comments if comment.startswith("# type:")]
        assert comments == allowed, f"{relative_path} contains comments: {comments}"
