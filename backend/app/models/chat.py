from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin, UtcDateTime, enum_type, utc_now
from app.models.deployment import Deployment


class SessionStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ChatSession(TimestampMixin, Base):
    """A conversation between the user and a deployed model."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id", ondelete="RESTRICT"))
    status: Mapped[SessionStatus] = mapped_column(
        enum_type(SessionStatus), default=SessionStatus.IDLE
    )
    error: Mapped[str | None] = mapped_column(Text)

    deployment: Mapped[Deployment] = relationship()
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        order_by="ChatMessage.id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(Base):
    """A single message in a chat session, including tool calls and tool results."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("bug_hunt_jobs.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(enum_type(MessageRole))
    content: Mapped[str | None] = mapped_column(Text)
    reasoning: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    tool_call_id: Mapped[str | None] = mapped_column(String(200))
    tool_name: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int | None]
    completion_tokens: Mapped[int | None]
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
