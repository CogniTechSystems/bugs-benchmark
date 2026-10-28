from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import ContextDep, DbDep, conflict, get_or_404
from app.database import utc_now
from app.models import BugHunt, BugHuntJob, JobScore, JobStatus, LanguageModel, Runtime
from app.schemas.jobs import JobDetail, JobSummary, LeaderboardEntry
from app.services.jobs import close_job

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs(
    db: DbDep,
    model_id: int | None = None,
    bug_hunt: str | None = None,
    job_status: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[JobSummary]:
    query = select(BugHuntJob).order_by(BugHuntJob.id.desc()).limit(limit)
    if model_id is not None:
        query = query.where(BugHuntJob.model_id == model_id)
    if bug_hunt:
        query = query.join(BugHunt).where(BugHunt.slug == bug_hunt)
    if job_status is not None:
        query = query.where(BugHuntJob.status == job_status)
    return [JobSummary.from_job(job) for job in db.scalars(query)]


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: DbDep) -> JobDetail:
    return JobDetail.from_job(get_or_404(db, BugHuntJob, job_id))


@router.post(
    "/jobs/{job_id}/finish", response_model=JobDetail, status_code=status.HTTP_202_ACCEPTED
)
def finish_job(job_id: int, context: ContextDep, db: DbDep) -> JobDetail:
    job = get_or_404(db, BugHuntJob, job_id)
    if job.status is not JobStatus.ACTIVE:
        raise conflict("Only active jobs can be finished.")
    close_job(job, "Finished from the user interface.")
    db.commit()
    context.scoring.schedule(job.id)
    return JobDetail.from_job(job)


@router.post(
    "/jobs/{job_id}/rescore", response_model=JobDetail, status_code=status.HTTP_202_ACCEPTED
)
def rescore_job(job_id: int, context: ContextDep, db: DbDep) -> JobDetail:
    job = get_or_404(db, BugHuntJob, job_id)
    if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED) or job.finished_at is None:
        raise conflict("Only finished jobs can be rescored.")
    job.status = JobStatus.SCORING
    db.commit()
    context.scoring.schedule(job.id)
    return JobDetail.from_job(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobDetail)
def cancel_job(job_id: int, db: DbDep) -> JobDetail:
    job = get_or_404(db, BugHuntJob, job_id)
    if job.status is not JobStatus.ACTIVE:
        raise conflict("Only active jobs can be cancelled.")
    job.status = JobStatus.CANCELLED
    job.finished_at = utc_now()
    job.duration_seconds = (job.finished_at - job.started_at).total_seconds()
    db.commit()
    return JobDetail.from_job(job)


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def leaderboard(db: DbDep, bug_hunt: str | None = None) -> list[LeaderboardEntry]:
    average_score = func.avg(JobScore.final_score)
    query = (
        select(
            BugHuntJob.model_id,
            LanguageModel.repo_id,
            BugHuntJob.runtime_id,
            Runtime.name,
            func.count(JobScore.id),
            average_score,
            func.max(JobScore.final_score),
            func.avg(JobScore.accuracy_score),
            func.avg(BugHuntJob.working_seconds),
            func.sum(JobScore.bugs_found),
            func.sum(JobScore.bugs_total),
            func.sum(JobScore.fixes_verified),
            func.sum(JobScore.false_positives),
        )
        .join(JobScore, JobScore.job_id == BugHuntJob.id)
        .join(LanguageModel, LanguageModel.id == BugHuntJob.model_id)
        .join(Runtime, Runtime.id == BugHuntJob.runtime_id)
        .where(BugHuntJob.status == JobStatus.COMPLETED)
        .group_by(BugHuntJob.model_id, LanguageModel.repo_id, BugHuntJob.runtime_id, Runtime.name)
        .order_by(average_score.desc())
    )
    if bug_hunt:
        query = query.join(BugHunt, BugHunt.id == BugHuntJob.bug_hunt_id).where(
            BugHunt.slug == bug_hunt
        )
    return [
        LeaderboardEntry(
            model_id=row[0],
            model_repo_id=row[1],
            runtime_id=row[2],
            runtime_name=row[3],
            jobs=row[4],
            average_final_score=round(row[5], 2),
            best_final_score=row[6],
            average_accuracy=round(row[7], 2),
            average_working_seconds=round(row[8] or 0.0, 1),
            bugs_found=row[9],
            bugs_total=row[10],
            fixes_verified=row[11],
            false_positives=row[12],
        )
        for row in db.execute(query)
    ]
