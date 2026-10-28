from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UtcDateTime, enum_type, utc_now
from app.models.chat import ChatSession
from app.models.deployment import Deployment
from app.models.language_model import LanguageModel
from app.models.runtime import Runtime


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class JobStatus(StrEnum):
    ACTIVE = "active"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FindingOutcome(StrEnum):
    MATCHED = "matched"
    SUPERSEDED = "superseded"
    FALSE_POSITIVE = "false_positive"


class FixStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class BugHunt(Base):
    """Catalogue entry mirroring a challenge definition on disk."""

    __tablename__ = "bug_hunts"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[Difficulty] = mapped_column(enum_type(Difficulty))
    language: Mapped[str] = mapped_column(String(50))
    summary: Mapped[str] = mapped_column(Text)
    bug_count: Mapped[int]
    max_points: Mapped[int]
    time_budget_seconds: Mapped[int]
    is_available: Mapped[bool] = mapped_column(default=True)
    synced_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class BugHuntJob(Base):
    """A single attempt by a deployed model to complete a bug hunt."""

    __tablename__ = "bug_hunt_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    bug_hunt_id: Mapped[int] = mapped_column(ForeignKey("bug_hunts.id", ondelete="RESTRICT"))
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="RESTRICT"), index=True
    )
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id", ondelete="RESTRICT"))
    model_id: Mapped[int] = mapped_column(
        ForeignKey("language_models.id", ondelete="RESTRICT"), index=True
    )
    runtime_id: Mapped[int] = mapped_column(ForeignKey("runtimes.id", ondelete="RESTRICT"))
    settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)

    status: Mapped[JobStatus] = mapped_column(enum_type(JobStatus), default=JobStatus.ACTIVE)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    duration_seconds: Mapped[float | None]
    working_seconds: Mapped[float | None]
    llm_calls: Mapped[int] = mapped_column(default=0)
    tool_calls: Mapped[int] = mapped_column(default=0)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    agent_summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    bug_hunt: Mapped[BugHunt] = relationship()
    session: Mapped[ChatSession] = relationship()
    deployment: Mapped[Deployment] = relationship()
    model: Mapped[LanguageModel] = relationship()
    runtime: Mapped[Runtime] = relationship()
    findings: Mapped[list["BugFinding"]] = relationship(
        back_populates="job",
        order_by="BugFinding.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bug_results: Mapped[list["JobBugResult"]] = relationship(
        back_populates="job",
        order_by="JobBugResult.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    score: Mapped["JobScore | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class BugFinding(Base):
    """A defect reported by the agent, with its proposed fix and scoring outcome."""

    __tablename__ = "bug_findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("bug_hunt_jobs.id", ondelete="CASCADE"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(500))
    line: Mapped[int]
    description: Mapped[str] = mapped_column(Text)
    original: Mapped[str] = mapped_column(Text)
    replacement: Mapped[str] = mapped_column(Text)
    outcome: Mapped[FindingOutcome | None] = mapped_column(enum_type(FindingOutcome))
    matched_bug_key: Mapped[str | None] = mapped_column(String(100))
    fix_status: Mapped[FixStatus | None] = mapped_column(enum_type(FixStatus))
    fix_details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    job: Mapped[BugHuntJob] = relationship(back_populates="findings")


class JobBugResult(Base):
    """Per-bug scoring outcome for a job."""

    __tablename__ = "job_bug_results"
    __table_args__ = (UniqueConstraint("job_id", "bug_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("bug_hunt_jobs.id", ondelete="CASCADE"))
    bug_key: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    points: Mapped[int]
    found: Mapped[bool]
    fix_verified: Mapped[bool]
    finding_id: Mapped[int | None] = mapped_column(
        ForeignKey("bug_findings.id", ondelete="SET NULL")
    )

    job: Mapped[BugHuntJob] = relationship(back_populates="bug_results")


class JobScore(Base):
    """Aggregate score for a completed job."""

    __tablename__ = "job_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("bug_hunt_jobs.id", ondelete="CASCADE"), unique=True
    )
    bugs_total: Mapped[int]
    bugs_found: Mapped[int]
    fixes_verified: Mapped[int]
    false_positives: Mapped[int]
    points_earned: Mapped[float]
    points_possible: Mapped[float]
    precision: Mapped[float]
    recall: Mapped[float]
    accuracy_score: Mapped[float]
    time_factor: Mapped[float]
    final_score: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    job: Mapped[BugHuntJob] = relationship(back_populates="score")
