"""Reconciliation of persisted state after the server restarts."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    BugHuntJob,
    ChatSession,
    Deployment,
    DeploymentStatus,
    DownloadStatus,
    JobStatus,
    LanguageModel,
    SessionStatus,
)

INTERRUPTED = "Interrupted by a server restart."


def recover_interrupted_work(db: Session) -> list[int]:
    """Reset work that cannot survive a restart and return jobs that still need scoring."""
    db.execute(
        update(Deployment)
        .where(Deployment.status.in_([DeploymentStatus.STARTING, DeploymentStatus.RUNNING]))
        .values(status=DeploymentStatus.STOPPED, pid=None)
    )
    db.execute(
        update(LanguageModel)
        .where(LanguageModel.status.in_([DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING]))
        .values(status=DownloadStatus.FAILED, error=INTERRUPTED)
    )
    db.execute(
        update(ChatSession)
        .where(ChatSession.status == SessionStatus.RUNNING)
        .values(status=SessionStatus.ERROR, error=INTERRUPTED)
    )
    pending = list(db.scalars(select(BugHuntJob.id).where(BugHuntJob.status == JobStatus.SCORING)))
    db.commit()
    return pending
