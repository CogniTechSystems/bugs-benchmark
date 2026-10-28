from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import ContextDep, DbDep, conflict, get_or_404
from app.context import AppContext
from app.models import (
    ChatMessage,
    ChatSession,
    Deployment,
    DeploymentStatus,
    MessageRole,
    SessionStatus,
)
from app.schemas.jobs import JobSummary
from app.schemas.sessions import (
    DraftRead,
    MessageCreate,
    SessionCreate,
    SessionDetail,
    SessionSummary,
)
from app.services.jobs import find_active_job

router = APIRouter(prefix="/sessions", tags=["sessions"])

DEFAULT_TITLE = "New session"
TITLE_LENGTH = 60


def _detail(db: DbDep, context: AppContext, chat_session: ChatSession) -> SessionDetail:
    job = find_active_job(db, chat_session.id)
    progress = context.agent.draft(chat_session.id)
    return SessionDetail.build(
        chat_session,
        JobSummary.from_job(job) if job else None,
        DraftRead.model_validate(progress) if progress else None,
    )


@router.get("", response_model=list[SessionSummary])
def list_sessions(db: DbDep) -> list[SessionSummary]:
    sessions = db.scalars(select(ChatSession).order_by(ChatSession.updated_at.desc()))
    return [SessionSummary.from_session(session) for session in sessions]


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, context: ContextDep, db: DbDep) -> SessionDetail:
    deployment = get_or_404(db, Deployment, payload.deployment_id)
    chat_session = ChatSession(
        title=(payload.title or "").strip() or DEFAULT_TITLE, deployment=deployment
    )
    db.add(chat_session)
    db.commit()
    return _detail(db, context, chat_session)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, context: ContextDep, db: DbDep) -> SessionDetail:
    return _detail(db, context, get_or_404(db, ChatSession, session_id))


@router.post(
    "/{session_id}/messages",
    response_model=SessionDetail,
    status_code=status.HTTP_202_ACCEPTED,
)
def send_message(
    session_id: int, payload: MessageCreate, context: ContextDep, db: DbDep
) -> SessionDetail:
    chat_session = get_or_404(db, ChatSession, session_id)
    if chat_session.status is SessionStatus.RUNNING:
        raise conflict("The agent is still responding to the previous message.")
    if chat_session.deployment.status is not DeploymentStatus.RUNNING:
        raise conflict(f"Deployment '{chat_session.deployment.name}' is not running.")

    content = payload.content.strip()
    if chat_session.title == DEFAULT_TITLE:
        chat_session.title = content[:TITLE_LENGTH]
    chat_session.messages.append(ChatMessage(role=MessageRole.USER, content=content))
    chat_session.status = SessionStatus.RUNNING
    chat_session.error = None
    db.commit()

    context.tasks.submit(context.agent.run_turn, chat_session.id)
    return _detail(db, context, chat_session)


@router.post("/{session_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_turn(session_id: int, context: ContextDep, db: DbDep) -> None:
    get_or_404(db, ChatSession, session_id)
    context.agent.request_cancel(session_id)
