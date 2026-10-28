import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.context import AppContext, build_context
from app.database import utc_now
from app.main import create_app
from app.models import (
    Deployment,
    DeploymentStatus,
    DownloadStatus,
    LanguageModel,
    Runtime,
    RuntimeKind,
)
from app.services.llm_client import (
    Completion,
    Endpoint,
    GenerationParameters,
    ProgressCallback,
    ToolCall,
)
from app.services.tasks import InlineTaskRunner


@dataclass
class ScriptedClient:
    """Chat client that replays a fixed sequence of completions."""

    completions: list[Completion]
    requests: list[list[dict[str, Any]]] = field(default_factory=list)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        parameters: GenerationParameters,
        on_progress: ProgressCallback | None = None,
    ) -> Completion:
        self.requests.append(messages)
        return self.completions.pop(0)


def tool_call(name: str, **arguments: Any) -> Completion:
    call = ToolCall(id=f"call_{name}_{len(arguments)}", name=name, arguments=json.dumps(arguments))
    return Completion(content=None, tool_calls=(call,), prompt_tokens=100, completion_tokens=20)


def reply(text: str, reasoning: str | None = None) -> Completion:
    return Completion(
        content=text, tool_calls=(), reasoning=reasoning, prompt_tokens=50, completion_tokens=10
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", frontend_dist_dir=tmp_path / "missing")


@pytest.fixture
def scripted_client() -> ScriptedClient:
    return ScriptedClient(completions=[])


@pytest.fixture
def context(settings: Settings, scripted_client: ScriptedClient) -> AppContext:
    def factory(_endpoint: Endpoint) -> ScriptedClient:
        return scripted_client

    app_context = build_context(settings, tasks=InlineTaskRunner(), client_factory=factory)
    app_context.initialise()
    return app_context


@pytest.fixture
def client(context: AppContext) -> Iterator[TestClient]:
    with TestClient(create_app(context)) as test_client:
        yield test_client


@pytest.fixture
def running_deployment(client: TestClient, context: AppContext, tmp_path: Path) -> int:
    """Insert a ready model and an external runtime, and mark the deployment as running."""
    with context.session_factory() as db:
        model = LanguageModel(
            repo_id="example/coder",
            local_path=str(tmp_path / "models" / "example__coder"),
            status=DownloadStatus.READY,
            completed_at=utc_now(),
        )
        runtime = Runtime(
            name="External",
            kind=RuntimeKind.EXTERNAL,
            base_url="http://127.0.0.1:9",
        )
        deployment = Deployment(
            name="Coder",
            model=model,
            runtime=runtime,
            status=DeploymentStatus.RUNNING,
        )
        db.add(deployment)
        db.commit()
        return deployment.id
