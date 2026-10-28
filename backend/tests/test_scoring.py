import pytest

from app.services.challenges import ExpectedBug
from app.services.scoring import BugOutcome, ReportedLocation, compute_score, match_findings


def bug(key: str, file: str, start: int, end: int | None = None) -> ExpectedBug:
    return ExpectedBug(
        key=key,
        title=key,
        file=file,
        points=1,
        tests=("tests/test_x.py::test_x",),
        original="",
        replacement="",
        line_start=start,
        line_end=end or start,
    )


BUGS = [
    bug("first", "pkg/a.py", 10),
    bug("second", "pkg/a.py", 20, 22),
    bug("third", "pkg/b.py", 5),
]


def test_findings_match_by_file_and_line_with_tolerance():
    locations = [
        ReportedLocation("pkg/a.py", 12),
        ReportedLocation("src/pkg/a.py", 21),
        ReportedLocation("pkg\\b.py", 5),
    ]
    assert match_findings(BUGS, locations, tolerance=2) == ["first", "second", "third"]


def test_findings_outside_tolerance_or_in_other_files_do_not_match():
    locations = [ReportedLocation("pkg/a.py", 15), ReportedLocation("pkg/c.py", 10)]
    assert match_findings(BUGS, locations, tolerance=2) == [None, None]


def test_repeated_findings_target_the_same_bug():
    locations = [ReportedLocation("pkg/a.py", 10), ReportedLocation("pkg/a.py", 11)]
    assert match_findings(BUGS, locations, tolerance=2) == ["first", "first"]


def test_score_rewards_detection_and_fixes_and_penalises_false_positives():
    outcomes = [BugOutcome(1, True, True), BugOutcome(2, True, False), BugOutcome(3, False, False)]
    summary = compute_score(
        outcomes,
        false_positives=1,
        duration_seconds=100,
        time_budget_seconds=600,
        false_positive_penalty=0.5,
        minimum_time_factor=0.5,
    )
    assert summary.points_possible == 12
    assert summary.points_earned == 3.5
    assert summary.accuracy_score == pytest.approx(29.17, abs=0.01)
    assert summary.time_factor == 1.0
    assert summary.precision == pytest.approx(2 / 3)
    assert summary.recall == pytest.approx(2 / 3)


def test_score_is_reduced_when_time_budget_is_exceeded():
    outcomes = [BugOutcome(1, True, True)]
    over_budget = compute_score(outcomes, 0, 800, 400, 0.5, 0.5)
    far_over_budget = compute_score(outcomes, 0, 4000, 400, 0.5, 0.5)
    assert over_budget.time_factor == 0.5
    assert over_budget.final_score == 50.0
    assert far_over_budget.time_factor == 0.5
    assert compute_score(outcomes, 0, 500, 400, 0.5, 0.5).time_factor == 0.8


def test_score_never_drops_below_zero():
    summary = compute_score([BugOutcome(1, False, False)], 10, 10, 100, 0.5, 0.5)
    assert summary.points_earned == 0
    assert summary.final_score == 0
