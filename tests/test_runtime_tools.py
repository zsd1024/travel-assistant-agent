from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from travel_assistant.config import Settings
from travel_assistant.memory import JsonPreferenceStore
from travel_assistant.models import TripPlan, TripRequest
from travel_assistant.runner import build_runner
from travel_assistant.tools.intake import make_record_command
from travel_assistant.tools.preferences import persist_preference


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        travel_agent_fake_model=True,
        travel_agent_prefs_path=str(tmp_path / "prefs.json"),
    )


def _record_call(cid: str = "c1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "record_trip_request",
            "args": {
                "origin": "Shanghai", "destination": "Tokyo",
                "duration_days": 5, "comfort_level": "comfort",
                "interests": ["food"],
            },
            "id": cid,
        }],
    )


def _tool_call(name: str, cid: str, args: dict | None = None) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args or {}, "id": cid}]
    )


def _tripplan_call(cid: str = "cp") -> AIMessage:
    return _tool_call(
        "TripPlan", cid, {"summary": "Shanghai->Tokyo 5d", "assumptions": ["m6"]}
    )


def test_make_record_command_unit() -> None:
    cmd = make_record_command(
        "c1", origin="Shanghai", destination="Tokyo",
        duration_days=5, comfort_level="comfort", interests=["food"],
    )
    tr = cmd.update["trip_request"]
    assert isinstance(tr, TripRequest)
    assert tr.destination == "Tokyo"
    assert tr.is_ready_to_plan() is True
    msg = cmd.update["messages"][0]
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "c1"


def test_persist_preference_partial(tmp_path: Path) -> None:
    from travel_assistant.models import ComfortLevel, UserPreferences
    store = JsonPreferenceStore(tmp_path / "p.json")
    store.save_user_preferences(
        UserPreferences(user_id="u1", liked_interests=["food"], home_city="Shanghai")
    )
    merged = persist_preference(
        store, "u1", {"preferred_comfort_level": "luxury", "home_city": ""}
    )
    assert merged.preferred_comfort_level == ComfortLevel.LUXURY
    assert merged.liked_interests == ["food"]      # preserved
    assert merged.home_city == "Shanghai"          # empty drop -> preserved
    assert store.load_user_preferences("u1") == merged


def test_record_trip_request_updates_state(tmp_path: Path) -> None:
    runner = build_runner(
        _settings(tmp_path),
        scripted_fake_messages=[_record_call(), _tripplan_call()],
    )
    r = runner.run("u1", "t1", "Shanghai to Tokyo 5 days comfort food")
    assert isinstance(r.trip_request, TripRequest)
    assert r.trip_request.destination == "Tokyo"
    assert isinstance(r.plan, TripPlan)


def test_domain_tool_reads_state_via_runtime(tmp_path: Path) -> None:
    runner = build_runner(
        _settings(tmp_path),
        scripted_fake_messages=[
            _record_call("c1"),
            _tool_call("search_flights_tool", "c2"),
            _tripplan_call(),
        ],
    )
    r = runner.run("u1", "t1", "plan it")
    # search_flights_tool read trip_request.destination from state -> "Tokyo"
    # appears in the flight option arrive field in the ToolMessage.
    assert any(
        isinstance(m, ToolMessage) and "Tokyo" in str(m.content)
        for m in r.messages
    )
    assert isinstance(r.plan, TripPlan)


def test_save_preference_writes_json_store(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    runner = build_runner(
        settings,
        scripted_fake_messages=[
            _tool_call(
                "save_preference", "c1",
                {"liked_interests": ["food"], "preferred_comfort_level": "comfort"},
            ),
            _tripplan_call(),
        ],
    )
    r = runner.run("u9", "t1", "remember I like food and comfort")
    saved = JsonPreferenceStore(settings.travel_agent_prefs_path).load_user_preferences(
        "u9"
    )
    assert saved is not None
    assert saved.liked_interests == ["food"]
    assert any(
        isinstance(m, ToolMessage) and "preferences saved" in str(m.content)
        for m in r.messages
    )
    assert isinstance(r.plan, TripPlan)
