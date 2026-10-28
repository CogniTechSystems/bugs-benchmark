"""Execution of agent turns: model calls interleaved with tool execution."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import ChatMessage, ChatSession, DeploymentStatus, MessageRole, SessionStatus
from app.services.agent.prompts import build_conversation
from app.services.agent.tools import ToolContext, execute_tool, tool_schemas
from app.services.challenges import ChallengeCatalog
from app.services.llm_client import ChatClientFactory, GenerationParameters, Progress
from app.services.runtime_manager import RuntimeManager
from app.services.scoring import ScoringService

logger = logging.getLogger(__name__)

PROGRESS_INTERVAL_SECONDS = 1.0


class AgentError(RuntimeError):
    """Raised when an agent turn cannot proceed."""


class AgentRunner:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
        catalog: ChallengeCatalog,
        scoring: ScoringService,
        runtime_manager: RuntimeManager,
        client_factory: ChatClientFactory,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._catalog = catalog
        self._scoring = scoring
        self._runtime_manager = runtime_manager
        self._client_factory = client_factory
        self._cancelled: set[int] = set()
        self._drafts: dict[int, Progress] = {}
        self._lock = threading.Lock()

    def draft(self, session_id: int) -> Progress | None:
        """Return the partial output of the model call currently running for a session."""
        with self._lock:
            return self._drafts.get(session_id)

    def request_cancel(self, session_id: int) -> None:
        with self._lock:
            self._cancelled.add(session_id)

    def run_turn(self, session_id: int) -> None:
        """Respond to the latest user message. Run as a background task."""
        with self._lock:
            self._cancelled.discard(session_id)
        with self._session_factory() as db:
            chat_session = db.get_one(ChatSession, session_id)
            try:
                self._run(db, chat_session)
                chat_session.status = SessionStatus.IDLE
                chat_session.error = None
            except Exception as exc:
                logger.exception("Agent turn failed for session %s", session_id)
                db.rollback()
                chat_session.status = SessionStatus.ERROR
                chat_session.error = str(exc)
            finally:
                self._clear_draft(session_id)
            db.commit()

    def _run(self, db: Session, chat_session: ChatSession) -> None:
        deployment = chat_session.deployment
        if deployment.status is not DeploymentStatus.RUNNING:
            raise AgentError(f"Deployment '{deployment.name}' is not running.")

        client = self._client_factory(self._runtime_manager.endpoint(deployment))
        parameters = GenerationParameters(
            temperature=deployment.temperature,
            top_p=deployment.top_p,
            max_tokens=deployment.max_tokens,
        )
        context = ToolContext(
            db=db,
            chat_session=chat_session,
            catalog=self._catalog,
            scoring=self._scoring,
            output_limit=self._settings.tool_output_limit,
        )
        tools = tool_schemas()

        for _ in range(self._settings.agent_max_iterations):
            if self._is_cancelled(chat_session.id):
                return

            job = context.active_job()
            started = time.perf_counter()
            completion = client.complete(
                build_conversation(chat_session.messages),
                tools,
                parameters,
                on_progress=self._progress_recorder(chat_session.id),
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._clear_draft(chat_session.id)

            chat_session.messages.append(
                ChatMessage(
                    job_id=job.id if job else None,
                    role=MessageRole.ASSISTANT,
                    content=completion.content,
                    reasoning=completion.reasoning,
                    tool_calls=[asdict(call) for call in completion.tool_calls] or None,
                    prompt_tokens=completion.prompt_tokens,
                    completion_tokens=completion.completion_tokens,
                    latency_ms=latency_ms,
                )
            )
            if job is not None:
                job.llm_calls += 1
                job.prompt_tokens += completion.prompt_tokens or 0
                job.completion_tokens += completion.completion_tokens or 0
            db.commit()

            if not completion.tool_calls:
                return

            for call in completion.tool_calls:
                job_before = context.active_job()
                tool_started = time.perf_counter()
                result = execute_tool(context, call.name, call.arguments)
                tool_latency_ms = int((time.perf_counter() - tool_started) * 1000)
                owner = job_before or context.active_job()
                if owner is not None:
                    owner.tool_calls += 1
                chat_session.messages.append(
                    ChatMessage(
                        job_id=owner.id if owner else None,
                        role=MessageRole.TOOL,
                        tool_call_id=call.id,
                        tool_name=call.name,
                        content=result,
                        latency_ms=tool_latency_ms,
                    )
                )
                db.commit()

        raise AgentError(
            f"Stopped after {self._settings.agent_max_iterations} model calls without a final "
            "answer. Send another message to continue."
        )

    def _progress_recorder(self, session_id: int) -> Callable[[Progress], None]:
        last_update = 0.0

        def record(progress: Progress) -> None:
            nonlocal last_update
            now = time.monotonic()
            if now - last_update < PROGRESS_INTERVAL_SECONDS:
                return
            last_update = now
            with self._lock:
                self._drafts[session_id] = progress

        return record

    def _clear_draft(self, session_id: int) -> None:
        with self._lock:
            self._drafts.pop(session_id, None)

    def _is_cancelled(self, session_id: int) -> bool:
        with self._lock:
            return session_id in self._cancelled
