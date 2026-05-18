"""JSON-file PreferenceStore keyed by user_id. Missing/corrupt files are safe."""
import json
from pathlib import Path
from typing import Any

from travel_assistant.models import UserPreferences


class JsonPreferenceStore:
    """A `PreferenceStore` backed by a single JSON object keyed by user_id."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _backup_path(self) -> Path:
        return self._path.with_name(self._path.name + ".bak")

    def _backup_corrupt(self) -> None:
        try:
            self._path.replace(self._backup_path())
        except OSError:
            pass

    def _read_all(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return {}
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            self._backup_corrupt()
            return {}
        if not isinstance(data, dict):
            self._backup_corrupt()
            return {}
        return data

    def load_user_preferences(self, user_id: str) -> UserPreferences | None:
        raw = self._read_all().get(user_id)
        if raw is None:
            return None
        return UserPreferences.model_validate(raw)

    def save_user_preferences(self, preferences: UserPreferences) -> None:
        data = self._read_all()
        data[preferences.user_id] = preferences.model_dump(mode="json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
        )

    def update_user_preferences(
        self, user_id: str, updates: dict[str, Any]
    ) -> UserPreferences:
        existing = self.load_user_preferences(user_id)
        base: dict[str, Any] = (
            existing.model_dump(mode="json") if existing is not None else {}
        )
        base.update(updates)
        base["user_id"] = user_id  # identity key is never overwritable
        merged = UserPreferences.model_validate(base)
        self.save_user_preferences(merged)
        return merged
