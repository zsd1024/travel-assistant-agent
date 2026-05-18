"""save_preference persistence helper (M3 JSON store, partial update)."""
from typing import Any

from travel_assistant.memory.repository import PreferenceStore
from travel_assistant.models import UserPreferences


def persist_preference(
    store: PreferenceStore, user_id: str, updates: dict[str, Any]
) -> UserPreferences:
    """Apply a partial preference update via the M3 store API. Empty / None
    values are dropped so unrelated stored fields are preserved."""
    clean = {k: v for k, v in updates.items() if v not in (None, "", [])}
    return store.update_user_preferences(user_id, clean)
