import os

import pytest

from travel_assistant.config import Settings
from travel_assistant.tracing import configure_tracing


@pytest.fixture(autouse=True)
def _restore_langsmith_env() -> None:
    keys = ("LANGSMITH_TRACING", "LANGSMITH_API_KEY")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    try:
        yield
    finally:
        for k in keys:
            if saved[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]


def test_tracing_disabled_by_default() -> None:
    assert configure_tracing(Settings(langsmith_tracing=False)) is False
    assert "LANGSMITH_TRACING" not in os.environ


def test_tracing_enabled_sets_env() -> None:
    assert configure_tracing(Settings(langsmith_tracing=True)) is True
    assert os.environ["LANGSMITH_TRACING"] == "true"


def test_tracing_propagates_user_key() -> None:
    configure_tracing(Settings(langsmith_tracing=True, langsmith_api_key="ls-xyz"))
    assert os.environ["LANGSMITH_API_KEY"] == "ls-xyz"


def test_tracing_never_hardcodes_key() -> None:
    configure_tracing(Settings(langsmith_tracing=True))
    assert "LANGSMITH_API_KEY" not in os.environ
