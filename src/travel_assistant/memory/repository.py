"""Long-term preference storage interface (swappable backend)."""
from typing import Any, Protocol

from travel_assistant.models import UserPreferences


class PreferenceStore(Protocol):
    """Persistence boundary for user travel preferences, keyed by user_id."""

    def load_user_preferences(self, user_id: str) -> UserPreferences | None:
        """Return stored preferences for user_id, or None if absent."""
        ...

    def save_user_preferences(self, preferences: UserPreferences) -> None:
        """Persist (insert or replace) the given preferences."""
        ...

    def update_user_preferences(
        self, user_id: str, updates: dict[str, Any]
    ) -> UserPreferences:
        """Apply a partial update; unrelated fields are preserved. Returns the
        merged, validated, persisted preferences."""
        ...
