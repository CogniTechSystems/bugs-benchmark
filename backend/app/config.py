"""Application settings loaded from environment variables prefixed with ``BHB_``."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BHB_",
        env_file=REPOSITORY_ROOT / ".env",
        extra="ignore",
    )

    data_dir: Path = REPOSITORY_ROOT / "data"
    database_url: str | None = None
    challenges_dir: Path = REPOSITORY_ROOT / "challenges"
    frontend_dist_dir: Path = REPOSITORY_ROOT / "frontend" / "dist"

    host: str = "127.0.0.1"
    port: int = 8000

    hf_token: str | None = None
    runtime_host: str = "127.0.0.1"
    runtime_stop_timeout_seconds: int = 15

    agent_max_iterations: int = 60
    tool_output_limit: int = 20_000

    scoring_timeout_seconds: int = 120
    line_tolerance: int = 2
    false_positive_penalty: float = 0.5
    minimum_time_factor: float = 0.5

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'bug_hunt_benchmark.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
