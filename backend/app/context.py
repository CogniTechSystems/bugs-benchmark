"""Construction and initialisation of the application's services."""

from dataclasses import dataclass

from huggingface_hub import HfApi
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database import create_database_engine, create_session_factory, run_migrations
from app.services.agent.runner import AgentRunner
from app.services.challenges import ChallengeCatalog
from app.services.huggingface import HubService
from app.services.llm_client import ChatClientFactory, OpenAICompatibleClient
from app.services.recovery import recover_interrupted_work
from app.services.runtime_manager import RuntimeManager
from app.services.scoring import ScoringService
from app.services.tasks import TaskRunner
from app.services.test_runner import TestRunner


@dataclass
class AppContext:
    settings: Settings
    session_factory: sessionmaker[Session]
    catalog: ChallengeCatalog
    tasks: TaskRunner
    runtime_manager: RuntimeManager
    hub: HubService
    scoring: ScoringService
    agent: AgentRunner

    def initialise(self) -> None:
        """Apply migrations, synchronise the catalogue and resume interrupted scoring."""
        run_migrations(self.settings.resolved_database_url)
        with self.session_factory() as db:
            self.catalog.sync(db)
            pending_jobs = recover_interrupted_work(db)
        for job_id in pending_jobs:
            self.scoring.schedule(job_id)

    def shutdown(self) -> None:
        self.runtime_manager.shutdown()
        self.tasks.shutdown()


def build_context(
    settings: Settings,
    *,
    tasks: TaskRunner | None = None,
    client_factory: ChatClientFactory = OpenAICompatibleClient,
    hub_api: HfApi | None = None,
) -> AppContext:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)

    session_factory = create_session_factory(create_database_engine(settings.resolved_database_url))
    tasks = tasks or TaskRunner()
    catalog = ChallengeCatalog(settings.challenges_dir)
    runtime_manager = RuntimeManager(settings, session_factory)
    scoring = ScoringService(
        settings, session_factory, catalog, tasks, TestRunner(settings.scoring_timeout_seconds)
    )
    agent = AgentRunner(
        settings, session_factory, catalog, scoring, runtime_manager, client_factory
    )
    return AppContext(
        settings=settings,
        session_factory=session_factory,
        catalog=catalog,
        tasks=tasks,
        runtime_manager=runtime_manager,
        hub=HubService(settings, session_factory, hub_api),
        scoring=scoring,
        agent=agent,
    )
