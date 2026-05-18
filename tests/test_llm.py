import pytest

from travel_assistant.config import Settings
from travel_assistant.llm import ModelConfigError, make_fake_model, resolve_model


def test_settings_defaults() -> None:
    s = Settings(travel_agent_fake_model=True)
    assert s.travel_agent_model_id == "deepseek:deepseek-chat"
    assert s.checkpointer_backend == "memory"
    assert s.travel_agent_fake_model is True


def test_model_id_and_provider_configurable() -> None:
    s = Settings(travel_agent_model_id="openai:gpt-4o", travel_agent_fake_model=True)
    assert s.travel_agent_model_id == "openai:gpt-4o"


def test_langsmith_env_read_but_no_logic() -> None:
    s = Settings(
        langsmith_tracing=True, langsmith_api_key="ls-key", travel_agent_fake_model=True
    )
    assert s.langsmith_tracing is True
    assert s.langsmith_api_key == "ls-key"


def test_invalid_checkpointer_backend_rejected() -> None:
    with pytest.raises(ValueError, match="CHECKPOINTER_BACKEND"):
        Settings(checkpointer_backend="redis", travel_agent_fake_model=True).validated()


def test_valid_checkpointer_backends_ok() -> None:
    for backend in ("memory", "sqlite"):
        s = Settings(checkpointer_backend=backend, travel_agent_fake_model=True)
        assert s.validated() is s


def test_fake_when_flag_enabled() -> None:
    s = Settings(travel_agent_fake_model=True, deepseek_api_key=None)
    model, is_fake = resolve_model(s)
    assert is_fake is True
    assert model is not None


def test_fake_model_is_bind_tools_capable() -> None:
    # Locks in the Task 2 spike finding: the fake must survive create_agent's
    # unconditional model.bind_tools(...) call.
    bound = make_fake_model().bind_tools([])
    assert bound is not None


def test_error_when_no_key_and_not_fake() -> None:
    s = Settings(travel_agent_fake_model=False, deepseek_api_key=None)
    with pytest.raises(ModelConfigError, match="DEEPSEEK_API_KEY"):
        resolve_model(s)


def test_real_model_path_uses_init_chat_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_init(model_id: str, **kwargs: object) -> object:
        captured["model_id"] = model_id
        captured["kwargs"] = kwargs
        return object()

    # setattr requires the attribute to already exist -> this also verifies
    # that `from langchain.chat_models import init_chat_model` is the correct
    # import path for the pinned langchain version.
    monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init)
    s = Settings(
        travel_agent_fake_model=False,
        deepseek_api_key="sk-test",
        travel_agent_model_id="deepseek:deepseek-chat",
    )
    model, is_fake = resolve_model(s)
    assert is_fake is False
    assert model is not None
    assert captured["model_id"] == "deepseek:deepseek-chat"
    assert isinstance(captured["kwargs"], dict)
    assert captured["kwargs"].get("api_key") == "sk-test"
