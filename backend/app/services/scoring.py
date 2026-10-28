"""Scoring of bug hunt jobs.

Scoring rules:

* A finding matches an expected bug when it names the same file and its line lies within the
  bug's line range, widened by ``line_tolerance`` on each side.
* When several findings match the same bug, only the most recent one is scored; earlier ones
  are marked as superseded and carry no penalty.
* A matched finding's fix is verified by applying it to a pristine copy of the project and
  running the hidden test suite. The fix is accepted when the bug's tests pass and every test
  unrelated to any expected bug still passes.
* Each bug is worth its ``points`` for detection and the same again for a verified fix.
  Every unmatched finding deducts ``false_positive_penalty`` points.
* The accuracy score is the percentage of available points earned. The final score multiplies
  accuracy by a time factor that falls from 1.0 once the time budget is exceeded, down to
  ``minimum_time_factor``. Time is working time: the duration of the job's model calls and
  tool executions, so waiting for the user or for a failed runtime is not counted.
"""

import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import (
    BugFinding,
    BugHuntJob,
    ChatMessage,
    FindingOutcome,
    FixStatus,
    JobBugResult,
    JobScore,
    JobStatus,
)
from app.services.challenges import (
    Challenge,
    ChallengeCatalog,
    ChallengeDefinitionError,
    ExpectedBug,
    normalise_source_path,
)
from app.services.code_edits import ChangeNotApplicableError, apply_change
from app.services.tasks import TaskRunner
from app.services.test_runner import TestRunner, expand_test_ids

logger = logging.getLogger(__name__)

MAX_REPORTED_FAILURES = 10


@dataclass(frozen=True)
class ReportedLocation:
    file_path: str
    line: int


@dataclass(frozen=True)
class BugOutcome:
    points: int
    found: bool
    fix_verified: bool


@dataclass(frozen=True)
class ScoreSummary:
    bugs_total: int
    bugs_found: int
    fixes_verified: int
    false_positives: int
    points_earned: float
    points_possible: float
    precision: float
    recall: float
    accuracy_score: float
    time_factor: float
    final_score: float


def match_findings(
    bugs: Sequence[ExpectedBug], locations: Sequence[ReportedLocation], tolerance: int
) -> list[str | None]:
    """Return the key of the bug each reported location matches, or ``None``."""
    matches: list[str | None] = []
    assigned: set[str] = set()
    for location in locations:
        path = normalise_source_path(location.file_path)
        candidates = [
            bug
            for bug in bugs
            if bug.file == path
            and bug.line_start - tolerance <= location.line <= bug.line_end + tolerance
        ]
        if not candidates:
            matches.append(None)
            continue
        best = min(
            candidates,
            key=lambda bug: (_distance(bug, location.line), bug.key in assigned),
        )
        assigned.add(best.key)
        matches.append(best.key)
    return matches


def compute_score(
    outcomes: Sequence[BugOutcome],
    false_positives: int,
    duration_seconds: float,
    time_budget_seconds: int,
    false_positive_penalty: float,
    minimum_time_factor: float,
) -> ScoreSummary:
    points_possible = float(2 * sum(outcome.points for outcome in outcomes))
    detection = sum(outcome.points for outcome in outcomes if outcome.found)
    fixes = sum(outcome.points for outcome in outcomes if outcome.fix_verified)
    points_earned = max(0.0, detection + fixes - false_positives * false_positive_penalty)

    bugs_found = sum(outcome.found for outcome in outcomes)
    reported = bugs_found + false_positives
    accuracy = 100.0 * points_earned / points_possible if points_possible else 0.0

    if duration_seconds <= time_budget_seconds:
        time_factor = 1.0
    else:
        time_factor = max(minimum_time_factor, time_budget_seconds / duration_seconds)

    return ScoreSummary(
        bugs_total=len(outcomes),
        bugs_found=bugs_found,
        fixes_verified=sum(outcome.fix_verified for outcome in outcomes),
        false_positives=false_positives,
        points_earned=points_earned,
        points_possible=points_possible,
        precision=bugs_found / reported if reported else 0.0,
        recall=bugs_found / len(outcomes) if outcomes else 0.0,
        accuracy_score=round(accuracy, 2),
        time_factor=round(time_factor, 4),
        final_score=round(accuracy * time_factor, 2),
    )


class ScoringService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        catalog: ChallengeCatalog,
        tasks: TaskRunner,
        test_runner: TestRunner,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._catalog = catalog
        self._tasks = tasks
        self._test_runner = test_runner

    def schedule(self, job_id: int) -> None:
        self._tasks.submit(self.score_job, job_id)

    def score_job(self, job_id: int) -> None:
        with self._session_factory() as db:
            job = db.get(BugHuntJob, job_id)
            if job is None:
                return
            try:
                self._score(db, job)
                job.status = JobStatus.COMPLETED
                job.error = None
            except Exception as exc:
                logger.exception("Scoring failed for job %s", job_id)
                db.rollback()
                job = db.get_one(BugHuntJob, job_id)
                job.status = JobStatus.FAILED
                job.error = f"Scoring failed: {exc}"
            db.commit()

    def _score(self, db: Session, job: BugHuntJob) -> None:
        challenge = self._catalog.get(job.bug_hunt.slug)
        job.bug_results.clear()
        job.score = None
        db.flush()

        latest = self._classify_findings(challenge, job.findings)

        baseline = self._test_runner.run(challenge)
        bug_tests = {
            bug.key: expand_test_ids(bug.tests, baseline.all_tests) for bug in challenge.bugs
        }
        missing = [key for key, tests in bug_tests.items() if not tests]
        if missing:
            raise ChallengeDefinitionError(f"No tests found for bugs: {', '.join(missing)}")
        regression_tests = baseline.all_tests.difference(*bug_tests.values())

        outcomes = []
        for bug in challenge.bugs:
            finding = latest.get(bug.key)
            fix_verified = False
            if finding is not None:
                required = bug_tests[bug.key] | regression_tests
                finding.fix_status, finding.fix_details = self._verify_fix(
                    challenge, finding, required
                )
                fix_verified = finding.fix_status is FixStatus.VERIFIED
            job.bug_results.append(
                JobBugResult(
                    bug_key=bug.key,
                    title=bug.title,
                    points=bug.points,
                    found=finding is not None,
                    fix_verified=fix_verified,
                    finding_id=finding.id if finding else None,
                )
            )
            outcomes.append(BugOutcome(bug.points, finding is not None, fix_verified))

        job.working_seconds = working_seconds(db, job)
        false_positives = sum(
            finding.outcome is FindingOutcome.FALSE_POSITIVE for finding in job.findings
        )
        summary = compute_score(
            outcomes,
            false_positives,
            job.working_seconds,
            challenge.time_budget_seconds,
            self._settings.false_positive_penalty,
            self._settings.minimum_time_factor,
        )
        job.score = JobScore(**asdict(summary))

    def _classify_findings(
        self, challenge: Challenge, findings: Sequence[BugFinding]
    ) -> dict[str, BugFinding]:
        locations = [ReportedLocation(finding.file_path, finding.line) for finding in findings]
        keys = match_findings(challenge.bugs, locations, self._settings.line_tolerance)
        latest = {key: finding for finding, key in zip(findings, keys, strict=True) if key}
        for finding, key in zip(findings, keys, strict=True):
            finding.matched_bug_key = key
            finding.fix_status = None
            finding.fix_details = None
            if key is None:
                finding.outcome = FindingOutcome.FALSE_POSITIVE
            elif latest[key] is finding:
                finding.outcome = FindingOutcome.MATCHED
            else:
                finding.outcome = FindingOutcome.SUPERSEDED
        return latest

    def _verify_fix(
        self, challenge: Challenge, finding: BugFinding, required_tests: set[str]
    ) -> tuple[FixStatus, str]:
        relative_path = normalise_source_path(finding.file_path)
        try:
            source_path = challenge.resolve_source_path(relative_path)
            content = source_path.read_text(encoding="utf-8")
            patched = apply_change(content, finding.original, finding.replacement, finding.line)
        except (FileNotFoundError, ChangeNotApplicableError) as exc:
            return FixStatus.NOT_APPLICABLE, str(exc)

        result = self._test_runner.run(challenge, {relative_path: patched})
        failing = sorted(required_tests - result.passed)
        if not failing:
            return FixStatus.VERIFIED, f"All {len(required_tests)} required tests passed."
        shown = ", ".join(failing[:MAX_REPORTED_FAILURES])
        remainder = len(failing) - MAX_REPORTED_FAILURES
        suffix = f" and {remainder} more" if remainder > 0 else ""
        return FixStatus.FAILED, f"Failing tests: {shown}{suffix}."


def working_seconds(db: Session, job: BugHuntJob) -> float:
    """Time the job spent in model calls and tool execution, excluding idle and stalled time."""
    total_ms = db.scalar(
        select(func.coalesce(func.sum(ChatMessage.latency_ms), 0)).where(
            ChatMessage.job_id == job.id
        )
    )
    return (total_ms or 0) / 1000


def _distance(bug: ExpectedBug, line: int) -> int:
    if bug.line_start <= line <= bug.line_end:
        return 0
    return min(abs(line - bug.line_start), abs(line - bug.line_end))
