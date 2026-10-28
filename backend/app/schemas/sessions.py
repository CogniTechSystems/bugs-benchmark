from datetime import datetime
from typing import Any

from pydantic import Field

from app.models import ChatSession, MessageRole, SessionStatus
from app.schemas.base import Schema
from app.schemas.jobs import JobSummary


class SessionCreate(Schema):
    deployment_id: int
    title: str | None = Field(default=None, max_length=200)


class MessageCreate(Schema):
    content: str = Field(min_length=1, max_length=50_000)


class MessageRead(Schema):
    id: int
    role: MessageRole
    content: str | None
    reasoning: str | None
    tool_calls: list[dict[str, Any]] | None
    tool_call_id: str | None
    tool_name: str | None
    job_id: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    created_at: datetime


class SessionSummary(Schema):
    id: int
    title: str
    deployment_id: int
    deployment_name: str
    status: SessionStatus
    error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_session(cls, session: ChatSession) -> "SessionSummary":
        return cls(**_summary_fields(session))


class DraftRead(Schema):
    """Partial output of the model call in progress."""

    reasoning: str
    content: str


class SessionDetail(SessionSummary):
    messages: list[MessageRead]
    active_job: JobSummary | None
    draft: DraftRead | None

    @classmethod
    def build(
        cls, session: ChatSession, active_job: JobSummary | None, draft: DraftRead | None
    ) -> "SessionDetail":
        return cls(
            **_summary_fields(session),
            messages=[MessageRead.model_validate(message) for message in session.messages],
            active_job=active_job,
            draft=draft,
        )


def _summary_fields(session: ChatSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title,
        "deployment_id": session.deployment_id,
        "deployment_name": session.deployment.name,
        "status": session.status,
        "error": session.error,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }
