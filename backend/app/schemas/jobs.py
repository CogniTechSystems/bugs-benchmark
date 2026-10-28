from datetime import datetime
from typing import Any

from app.models import (
    BugHuntJob,
    Difficulty,
    FindingOutcome,
    FixStatus,
    JobStatus,
)
from app.schemas.base import Schema


class BugHuntRead(Schema):
    id: int
    slug: str
    title: str
    difficulty: Difficulty
    language: str
    summary: str
    bug_count: int
    max_points: int
    time_budget_seconds: int


class ScoreRead(Schema):
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
    created_at: datetime


class FindingRead(Schema):
    id: int
    file_path: str
    line: int
    description: str
    original: str
    replacement: str
    outcome: FindingOutcome | None
    matched_bug_key: str | None
    fix_status: FixStatus | None
    fix_details: str | None
    created_at: datetime


class BugResultRead(Schema):
    bug_key: str
    title: str
    points: int
    found: bool
    fix_verified: bool
    finding_id: int | None


class JobSummary(Schema):
    id: int
    bug_hunt_slug: str
    bug_hunt_title: str
    difficulty: Difficulty
    session_id: int
    model_id: int
    model_repo_id: str
    runtime_name: str
    deployment_name: str
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    working_seconds: float | None
    llm_calls: int
    tool_calls: int
    prompt_tokens: int
    completion_tokens: int
    findings_count: int
    final_score: float | None
    error: str | None

    @classmethod
    def from_job(cls, job: BugHuntJob) -> "JobSummary":
        return cls(**_summary_fields(job))


class JobDetail(JobSummary):
    settings_snapshot: dict[str, Any]
    agent_summary: str | None
    findings: list[FindingRead]
    bug_results: list[BugResultRead]
    score: ScoreRead | None

    @classmethod
    def from_job(cls, job: BugHuntJob) -> "JobDetail":
        return cls(
            **_summary_fields(job),
            settings_snapshot=job.settings_snapshot,
            agent_summary=job.agent_summary,
            findings=[FindingRead.model_validate(finding) for finding in job.findings],
            bug_results=[BugResultRead.model_validate(result) for result in job.bug_results],
            score=ScoreRead.model_validate(job.score) if job.score else None,
        )


class LeaderboardEntry(Schema):
    model_id: int
    model_repo_id: str
    runtime_id: int
    runtime_name: str
    jobs: int
    average_final_score: float
    best_final_score: float
    average_accuracy: float
    average_working_seconds: float
    bugs_found: int
    bugs_total: int
    fixes_verified: int
    false_positives: int


def _summary_fields(job: BugHuntJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "bug_hunt_slug": job.bug_hunt.slug,
        "bug_hunt_title": job.bug_hunt.title,
        "difficulty": job.bug_hunt.difficulty,
        "session_id": job.session_id,
        "model_id": job.model_id,
        "model_repo_id": job.model.repo_id,
        "runtime_name": job.runtime.name,
        "deployment_name": job.deployment.name,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "duration_seconds": job.duration_seconds,
        "working_seconds": job.working_seconds,
        "llm_calls": job.llm_calls,
        "tool_calls": job.tool_calls,
        "prompt_tokens": job.prompt_tokens,
        "completion_tokens": job.completion_tokens,
        "findings_count": len(job.findings),
        "final_score": job.score.final_score if job.score else None,
        "error": job.error,
    }
