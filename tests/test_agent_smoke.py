from pathlib import Path

from langchain_core.messages import AIMessage

from travel_assistant.config import Settings
from travel_assistant.memory import JsonPreferenceStore
from travel_assistant.models import ComfortLevel, TripPlan, UserPreferences
from travel_assistant.runner import _preferences_block, build_runner


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        travel_agent_fake_model=True,
        travel_agent_prefs_path=str(tmp_path / "prefs.json"),
    )


def test_agent_emits_structured_trip_plan(tmp_path: Path) -> None:
    scripted = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "TripPlan",
                    "args": {
                        "summary": "Shanghai to Tokyo, 5 days (comfort)",
                        "assumptions": ["fake-model test run"],
                    },
                    "id": "call_1",
                }
            ],
        )
    ]
    runner = build_runner(_settings(tmp_path), scripted_fake_messages=scripted)
    result = runner.run(
        user_id="u1", thread_id="t1",
        message="Shanghai to Tokyo, 5 days, comfort, food",
    )
    assert isinstance(result.plan, TripPlan)
    assert result.plan.summary == "Shanghai to Tokyo, 5 days (comfort)"
    assert result.plan.assumptions == ["fake-model test run"]


def test_preferences_block_reflects_saved_prefs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = JsonPreferenceStore(settings.travel_agent_prefs_path)
    store.save_user_preferences(
        UserPreferences(
            user_id="u1",
            liked_interests=["food"],
            preferred_comfort_level=ComfortLevel.COMFORT,
        )
    )
    block = _preferences_block(store.load_user_preferences("u1"))
    assert "food" in block
    assert "comfort" in block.lower()


def test_preferences_block_graceful_when_absent() -> None:
    assert "none on file" in _preferences_block(None)
