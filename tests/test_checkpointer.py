from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from travel_assistant.checkpointer import make_checkpointer
from travel_assistant.config import Settings
from travel_assistant.models import TripPlan, TripRequest
from travel_assistant.runner import build_runner


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


def _tripplan_call(cid: str = "cp") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{
            "name": "TripPlan",
            "args": {"summary": "S->T 5d", "assumptions": ["m7"]},
            "id": cid,
        }],
    )


def _memory_settings(tmp_path: Path) -> Settings:
    return Settings(
        travel_agent_fake_model=True,
        travel_agent_prefs_path=str(tmp_path / "prefs.json"),
    )


def _sqlite_settings(tmp_path: Path) -> Settings:
    return Settings(
        checkpointer_backend="sqlite",
        travel_agent_sqlite_path=str(tmp_path / "sub" / "cp.sqlite3"),
        travel_agent_prefs_path=str(tmp_path / "prefs.json"),
        travel_agent_fake_model=True,
    )


def test_factory_memory_is_default() -> None:
    saver = make_checkpointer(Settings(travel_agent_fake_model=True))
    assert isinstance(saver, InMemorySaver)


def test_factory_sqlite_when_configured(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "cp.sqlite3"
    settings = Settings(
        checkpointer_backend="sqlite",
        travel_agent_sqlite_path=str(db),
        travel_agent_fake_model=True,
    )
    saver = make_checkpointer(settings)
    assert "Sqlite" in type(saver).__name__
    assert db.parent.is_dir()
    assert db.exists()


def test_invalid_backend_rejected() -> None:
    with pytest.raises(ValueError, match="CHECKPOINTER_BACKEND"):
        make_checkpointer(
            Settings(checkpointer_backend="redis", travel_agent_fake_model=True)
        )


def test_same_thread_preserves_state(tmp_path: Path) -> None:
    runner = build_runner(
        _memory_settings(tmp_path),
        scripted_fake_messages=[
            _record_call(), _tripplan_call("cp1"),  # invoke #1 (thread A)
            _tripplan_call("cp2"),                   # invoke #2 (thread A)
        ],
    )
    r1 = runner.run("u1", "A", "Shanghai to Tokyo 5 days comfort food")
    assert isinstance(r1.trip_request, TripRequest)
    assert r1.trip_request.destination == "Tokyo"

    # Same thread, NO re-record: trip_request must survive from checkpoint.
    r2 = runner.run("u1", "A", "now plan it")
    assert isinstance(r2.trip_request, TripRequest)
    assert r2.trip_request.destination == "Tokyo"
    assert isinstance(r2.plan, TripPlan)


def test_different_thread_isolates_state(tmp_path: Path) -> None:
    runner = build_runner(
        _memory_settings(tmp_path),
        scripted_fake_messages=[
            _record_call(), _tripplan_call("cp1"),  # invoke #1 (thread A)
            _tripplan_call("cp2"),                   # invoke #2 (thread B)
        ],
    )
    runner.run("u1", "A", "Shanghai to Tokyo 5 days comfort food")
    r2 = runner.run("u1", "B", "fresh conversation")
    assert r2.trip_request is None


def test_sqlite_roundtrip_state(tmp_path: Path) -> None:
    runner = build_runner(
        _sqlite_settings(tmp_path),
        scripted_fake_messages=[
            _record_call(), _tripplan_call("cp1"),  # invoke #1 (thread A)
            _tripplan_call("cp2"),                   # invoke #2 (thread A)
        ],
    )
    r1 = runner.run("u1", "A", "Shanghai to Tokyo 5 days comfort food")
    assert isinstance(r1.trip_request, TripRequest)
    assert r1.trip_request.destination == "Tokyo"

    # Resume on the SAME thread: forces deserialization of the persisted
    # TripRequest / TripPlan through the sqlite serde. Must not raise.
    r2 = runner.run("u1", "A", "now plan it")
    assert isinstance(r2.trip_request, TripRequest)
    assert r2.trip_request.destination == "Tokyo"
    assert isinstance(r2.plan, TripPlan)


def test_sqlite_roundtrip_under_strict_msgpack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The msgpack allowlist (travel_assistant.models) is wired into the sqlite
    # serde, so the sqlite path stays safe even under strict mode (where
    # unregistered types are HARD-blocked instead of warned).
    monkeypatch.setenv("LANGGRAPH_STRICT_MSGPACK", "true")
    runner = build_runner(
        _sqlite_settings(tmp_path),
        scripted_fake_messages=[
            _record_call(), _tripplan_call("cp1"),
            _tripplan_call("cp2"),
        ],
    )
    runner.run("u1", "A", "Shanghai to Tokyo 5 days comfort food")
    r2 = runner.run("u1", "A", "now plan it")
    assert isinstance(r2.trip_request, TripRequest)
    assert r2.trip_request.destination == "Tokyo"
    assert isinstance(r2.plan, TripPlan)
