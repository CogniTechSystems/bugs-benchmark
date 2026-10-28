"""Creating and closing bug hunt jobs."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import utc_now
from app.models import BugHunt, BugHuntJob, ChatSession, JobStatus


def find_active_job(db: Session, session_id: int) -> BugHuntJob | None:
    return db.scalar(
        select(BugHuntJob)
        .where(BugHuntJob.session_id == session_id, BugHuntJob.status == JobStatus.ACTIVE)
        .order_by(BugHuntJob.id.desc())
        .limit(1)
    )


def start_job(db: Session, chat_session: ChatSession, bug_hunt: BugHunt) -> BugHuntJob:
    deployment = chat_session.deployment
    job = BugHuntJob(
        bug_hunt=bug_hunt,
        session_id=chat_session.id,
        deployment_id=deployment.id,
        model_id=deployment.model_id,
        runtime_id=deployment.runtime_id,
        settings_snapshot=deployment.settings_snapshot(),
    )
    db.add(job)
    db.flush()
    return job


def close_job(job: BugHuntJob, summary: str | None = None) -> None:
    """Stop the clock on an active job and mark it ready for scoring."""
    finished_at = utc_now()
    job.finished_at = finished_at
    job.duration_seconds = (finished_at - job.started_at).total_seconds()
    job.agent_summary = summary
    job.status = JobStatus.SCORING
