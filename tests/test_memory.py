from pathlib import Path

from travel_assistant.memory import JsonPreferenceStore
from travel_assistant.memory.repository import PreferenceStore
from travel_assistant.models import ComfortLevel, UserPreferences


def test_empty_store_returns_none(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "p.json")
    assert store.load_user_preferences("nobody") is None


def test_missing_file_is_graceful(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "nope" / "absent.json")
    assert store.load_user_preferences("u1") is None


def test_save_load_roundtrip(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "p.json")
    prefs = UserPreferences(
        user_id="u1",
        liked_interests=["food", "city walks"],
        preferred_comfort_level=ComfortLevel.COMFORT,
        pace_notes="relaxed",
        dietary_notes="vegetarian",
        home_city="Shanghai",
    )
    store.save_user_preferences(prefs)
    loaded = store.load_user_preferences("u1")
    assert loaded is not None
    assert loaded == prefs


def test_user_isolation(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "p.json")
    store.save_user_preferences(
        UserPreferences(user_id="u1", liked_interests=["food"])
    )
    store.save_user_preferences(
        UserPreferences(user_id="u2", liked_interests=["history"])
    )
    u1 = store.load_user_preferences("u1")
    u2 = store.load_user_preferences("u2")
    assert u1 is not None and u1.liked_interests == ["food"]
    assert u2 is not None and u2.liked_interests == ["history"]


def test_update_preserves_unrelated_fields(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "p.json")
    store.save_user_preferences(
        UserPreferences(
            user_id="u1",
            liked_interests=["food"],
            preferred_comfort_level=ComfortLevel.BUDGET,
            home_city="Shanghai",
        )
    )
    updated = store.update_user_preferences(
        "u1", {"preferred_comfort_level": "luxury", "user_id": "hacker"}
    )
    assert updated.preferred_comfort_level == ComfortLevel.LUXURY
    assert updated.liked_interests == ["food"]
    assert updated.home_city == "Shanghai"
    assert updated.user_id == "u1"
    persisted = store.load_user_preferences("u1")
    assert persisted == updated


def test_update_on_empty_creates(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "p.json")
    created = store.update_user_preferences("new", {"home_city": "Tokyo"})
    assert created.user_id == "new"
    assert created.home_city == "Tokyo"
    assert store.load_user_preferences("new") == created


def test_corrupt_file_recovers_and_backs_up(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text("{ not valid json", encoding="utf-8")
    store = JsonPreferenceStore(path)
    assert store.load_user_preferences("u1") is None
    backup = path.with_name(path.name + ".bak")
    assert backup.exists()
    store.save_user_preferences(UserPreferences(user_id="u1"))
    assert store.load_user_preferences("u1") is not None


def test_protocol_is_satisfied(tmp_path: Path) -> None:
    store: PreferenceStore = JsonPreferenceStore(tmp_path / "p.json")
    assert store.load_user_preferences("x") is None
