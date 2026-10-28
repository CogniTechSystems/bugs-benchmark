from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import ContextDep, DbDep
from app.models import BugHunt
from app.schemas.jobs import BugHuntRead
from app.services.agent.tools import DIFFICULTY_ORDER

router = APIRouter(prefix="/bug-hunts", tags=["bug hunts"])


def _available(db: DbDep) -> list[BugHunt]:
    hunts = db.scalars(select(BugHunt).where(BugHunt.is_available))
    return sorted(hunts, key=lambda hunt: (DIFFICULTY_ORDER[hunt.difficulty], hunt.slug))


@router.get("", response_model=list[BugHuntRead])
def list_bug_hunts(db: DbDep) -> list[BugHunt]:
    return _available(db)


@router.post("/reload", response_model=list[BugHuntRead])
def reload_bug_hunts(context: ContextDep, db: DbDep) -> list[BugHunt]:
    context.catalog.reload()
    context.catalog.sync(db)
    return _available(db)
