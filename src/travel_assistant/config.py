"""Application configuration loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_CHECKPOINTER_BACKENDS = {"memory", "sqlite"}
_VALID_PROVIDER_VALUES = {"mock", "amap"}
_PROVIDER_FIELDS: tuple[str, ...] = (
    "travel_agent_provider_poi",
    "travel_agent_provider_weather",
    "travel_agent_provider_route",
    "travel_agent_provider_geocoding",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # V0 fields (unchanged)
    deepseek_api_key: str | None = None
    travel_agent_model_id: str = "deepseek:deepseek-chat"
    travel_agent_fake_model: bool = False
    checkpointer_backend: str = "memory"
    travel_agent_sqlite_path: str = "data/checkpoints.sqlite3"
    travel_agent_prefs_path: str = "data/preferences.json"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None

    # V1 Amap additions
    amap_api_key: str | None = None
    amap_base_url: str = "https://restapi.amap.com/v3"
    travel_agent_provider_poi: str = "mock"
    travel_agent_provider_weather: str = "mock"
    travel_agent_provider_route: str = "mock"
    travel_agent_provider_geocoding: str = "mock"
    amap_request_timeout_s: float = 8.0
    amap_max_retries: int = 2
    amap_cache_max_entries: int = 256

    def validated(self) -> "Settings":
        if self.checkpointer_backend not in _VALID_CHECKPOINTER_BACKENDS:
            raise ValueError(
                "CHECKPOINTER_BACKEND must be one of "
                f"{sorted(_VALID_CHECKPOINTER_BACKENDS)}, got "
                f"{self.checkpointer_backend!r}"
            )
        for field in _PROVIDER_FIELDS:
            value = getattr(self, field)
            if value not in _VALID_PROVIDER_VALUES:
                raise ValueError(
                    f"{field.upper()} must be one of "
                    f"{sorted(_VALID_PROVIDER_VALUES)}, got {value!r}"
                )
        amap_selected = [
            f for f in _PROVIDER_FIELDS if getattr(self, f) == "amap"
        ]
        if amap_selected and not self.amap_api_key:
            raise ValueError(
                "AMAP_API_KEY is required when any of "
                f"{[f.upper() for f in amap_selected]} is set to 'amap'."
            )
        return self
