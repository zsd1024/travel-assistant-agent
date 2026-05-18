import pytest


@pytest.fixture(autouse=True)
def _force_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_FAKE_MODEL", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
