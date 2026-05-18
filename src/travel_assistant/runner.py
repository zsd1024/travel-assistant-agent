"""Runner: load prefs -> inject into the agent's system prompt -> invoke."""
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import InMemorySaver

from travel_assistant.agent import build_agent
from travel_assistant.config import Settings
from travel_assistant.llm import make_fake_model, resolve_model
from travel_assistant.memory import JsonPreferenceStore
from travel_assistant.models import TripPlan, TripRequest, UserPreferences
from travel_assistant.tools.runtime_tools import build_tools


@dataclass
class RunResult:
    plan: TripPlan | None
    messages: list[BaseMessage]
    trip_request: TripRequest | None = None


def _preferences_block(prefs: UserPreferences | None) -> str:
    if prefs is None:
        return "Known traveler preferences: none on file."
    return (
        "Known traveler preferences: "
        f"interests={prefs.liked_interests}, "
        f"comfort={prefs.preferred_comfort_level}, "
        f"pace={prefs.pace_notes!r}, diet={prefs.dietary_notes!r}, "
        f"home_city={prefs.home_city!r}."
    )


def _as_trip_request(raw: Any) -> TripRequest | None:
    if raw is None or isinstance(raw, TripRequest):
        return raw
    return TripRequest.model_validate(raw)


class Runner:
    def __init__(
        self,
        model: BaseChatModel,
        store: JsonPreferenceStore,
        tools_override: list[Any] | None,
        checkpointer: Any,
    ) -> None:
        self._model = model
        self._store = store
        self._tools_override = tools_override
        self._checkpointer = checkpointer

    def run(self, user_id: str, thread_id: str, message: str) -> RunResult:
        prefs = self._store.load_user_preferences(user_id)
        tools = (
            self._tools_override
            if self._tools_override is not None
            else build_tools(self._store, user_id)
        )
        agent = build_agent(
            self._model, tools, self._checkpointer, _preferences_block(prefs)
        )
        out = agent.invoke(
            {"messages": [("user", message)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        return RunResult(
            plan=out.get("structured_response"),
            messages=out.get("messages", []),
            trip_request=_as_trip_request(out.get("trip_request")),
        )


def build_runner(
    settings: Settings,
    *,
    scripted_fake_messages: list[AIMessage] | None = None,
    tools: list[Any] | None = None,
) -> Runner:
    settings.validated()
    if scripted_fake_messages is not None:
        model: BaseChatModel = make_fake_model(scripted_fake_messages)
    else:
        model, _ = resolve_model(settings)
    store = JsonPreferenceStore(settings.travel_agent_prefs_path)
    return Runner(model, store, tools, InMemorySaver())
