"""M8 CLI UX tests: --help contract, fake one-shot plan, friendly no-key error.

All deterministic and offline. The autouse conftest forces fake mode and
deletes DEEPSEEK_API_KEY; the no-key test overrides that explicitly.
"""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from travel_assistant.cli import app


def test_help_still_identifies_app() -> None:
    # Preserve the M0 contract (tests/test_smoke.py::test_cli_help_runs).
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Travel Assistant" in result.output


def test_fake_once_prints_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_PREFS_PATH", str(tmp_path / "prefs.json"))
    result = CliRunner().invoke(
        app,
        [
            "plan",
            "--fake",
            "--once",
            "--message",
            "Shanghai to Tokyo 5 days comfort food",
            "--user-id",
            "u1",
            "--thread-id",
            "t1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "*** FAKE MODEL ***" in result.output
    assert "Trip Plan" in result.output


def test_no_key_not_fake_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_FAKE_MODEL", "false")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("TRAVEL_AGENT_PREFS_PATH", str(tmp_path / "prefs.json"))
    result = CliRunner().invoke(app, ["plan", "--once", "--message", "x"])
    assert result.exit_code != 0
    assert "DEEPSEEK_API_KEY" in result.output
