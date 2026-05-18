"""Application configuration loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_CHECKPOINTER_BACKENDS = {"memory", "sqlite"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str | None = None
    travel_agent_model_id: str = "deepseek:deepseek-chat"
    travel_agent_fake_model: bool = False
    checkpointer_backend: str = "memory"
    travel_agent_sqlite_path: str = "data/checkpoints.sqlite3"
    travel_agent_prefs_path: str = "data/preferences.json"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None

    def validated(self) -> "Settings":
        if self.checkpointer_backend not in _VALID_CHECKPOINTER_BACKENDS:
            raise ValueError(
                "CHECKPOINTER_BACKEND must be one of "
                f"{sorted(_VALID_CHECKPOINTER_BACKENDS)}, got "
                f"{self.checkpointer_backend!r}"
            )
        return self
