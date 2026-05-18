"""API compatibility spike: verifies LangChain 1.x / LangGraph API shapes.

KEPT intentionally (not throwaway). Every fact asserted here was verified
empirically against the pinned versions. See
``docs/superpowers/notes/api-spike-findings.md`` for the authoritative summary
that later tasks (M5/M6) must follow where it differs from the original plan.

Verified import paths (pinned: langchain==1.3.1, langchain-core==1.4.0,
langgraph==1.2.0):

- ``from langchain.agents import create_agent``
- ``from langchain.agents import AgentState``  (real agent-state base)
- ``from langchain.tools import ToolRuntime``  (also re-exported by
  langgraph.prebuilt; langchain.tools is the canonical LangChain path)
- ``from langgraph.types import Command``
- ``from langchain_core.messages import AIMessage, ToolMessage``
- ``from langgraph.checkpoint.memory import InMemorySaver``
- ``from langchain_core.language_models.fake_chat_models import GenericFakeChatModel``
"""

from collections.abc import Sequence
from typing import Any

from langchain.agents import AgentState, create_agent
from langchain.tools import ToolRuntime
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel


class ScriptedFakeChatModel(GenericFakeChatModel):
    """GenericFakeChatModel + a no-op ``bind_tools``.

    VERIFIED DEVIATION: the stock ``GenericFakeChatModel`` (and every other
    fake chat model in ``langchain_core``) does NOT implement ``bind_tools``;
    the base implementation raises ``NotImplementedError``. ``create_agent``
    always calls ``model.bind_tools(...)`` when tools / structured output are
    present, so a deterministic spike/test model MUST override it. Returning
    ``self`` is safe because the scripted ``AIMessage``s already carry the
    tool calls; binding is a no-op for a fake.
    """

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[Any, Any]:
        return self


class SpikePlan(BaseModel):
    """Trivial structured-output model (NOT the real TripPlan)."""

    title: str


class SpikeState(AgentState):
    """Extends the real agent-state base with one extra key.

    This is exactly the pattern M5's ``state.py`` must use: subclass
    ``langchain.agents.AgentState`` (a ``TypedDict``-style ``dict`` subclass)
    and add domain keys. The extra key is read back via ToolRuntime and is
    persisted by the checkpointer across invokes on the same thread.
    """

    spike_value: str | None


def _make_agent() -> object:
    """Build a minimal agent. Returns the compiled graph."""

    def remember(text: str, runtime: ToolRuntime) -> Command:
        """A tool that reads runtime state and returns a Command state update.

        - ``runtime: ToolRuntime`` is auto-injected (NO Annotated wrapper).
        - ``runtime.state`` exposes the current (custom) state dict.
        - ``runtime.tool_call_id`` is the current tool call id.
        - Returning ``Command(update={...})`` both sets the custom state key
          AND appends a ToolMessage to ``messages``.
        """
        prior = runtime.state.get("spike_value")
        assert "messages" in runtime.state
        assert runtime.tool_call_id is not None
        return Command(
            update={
                "spike_value": f"{prior}|{text}" if prior else text,
                "messages": [
                    ToolMessage(
                        content=f"remembered:{text}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )

    # GenericFakeChatModel yields each provided message in order. Non-str
    # messages pass through unchanged, so we can script tool calls.
    #
    # VERIFIED model-loop shape: ONE invoke that does a tool call then a
    # structured response = exactly TWO model calls:
    #   1. model emits the "remember" tool call -> tool runs
    #   2. model emits the "SpikePlan" tool call -> agent parses structured
    #      output, appends a synthetic ToolMessage, and STOPS (no 3rd call).
    #
    # response_format=SpikePlan (a raw schema) -> AutoStrategy -> for a model
    # with profile=None it falls back to ToolStrategy: the model MUST emit a
    # tool call named after the schema class ("SpikePlan") whose args match
    # the schema. The agent parses that into result["structured_response"].
    #
    # We script three invokes (2 calls each = 6 scripted messages):
    #   - invoke 1 + 2 on thread spike-thread-1 (checkpoint resume)
    #   - invoke 3 on thread spike-thread-2 (isolation check)
    scripted = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "remember", "args": {"text": "alpha"}, "id": "call_1"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "SpikePlan",
                        "args": {"title": "Spike Trip"},
                        "id": "call_2",
                    }
                ],
            ),
            # Second invoke on the same thread: another tool call then the
            # structured-output tool call again.
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "remember", "args": {"text": "beta"}, "id": "call_3"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "SpikePlan",
                        "args": {"title": "Spike Trip 2"},
                        "id": "call_4",
                    }
                ],
            ),
            # Third invoke on a DIFFERENT thread: starts fresh (no leaked
            # spike_value). It still needs its own 2 scripted model calls.
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "remember", "args": {"text": "gamma"}, "id": "call_5"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "SpikePlan",
                        "args": {"title": "Spike Trip 3"},
                        "id": "call_6",
                    }
                ],
            ),
        ]
    )
    model = ScriptedFakeChatModel(messages=scripted)
    return create_agent(
        model=model,
        tools=[remember],
        response_format=SpikePlan,
        state_schema=SpikeState,
        checkpointer=InMemorySaver(),
    )


def test_create_agent_tool_command_structured_output_and_checkpointer() -> None:
    agent = _make_agent()
    config = {"configurable": {"thread_id": "spike-thread-1"}}

    # --- First invoke ---
    result = agent.invoke({"messages": [("user", "remember alpha")]}, config=config)

    # response_format result lands under "structured_response".
    assert isinstance(result["structured_response"], SpikePlan)
    assert result["structured_response"].title == "Spike Trip"

    # The Command(update=...) appended a ToolMessage into messages.
    assert any(
        isinstance(m, ToolMessage) and "remembered:alpha" in m.content
        for m in result["messages"]
    )

    # The Command(update=...) set the custom AgentState key.
    assert result["spike_value"] == "alpha"

    # --- Second invoke, SAME thread_id ---
    # Checkpointer must have persisted prior state; the tool reads the prior
    # spike_value via runtime.state and appends to it.
    result2 = agent.invoke({"messages": [("user", "remember beta")]}, config=config)

    # Prior custom state was visible to the tool and accumulated -> proves
    # InMemorySaver + thread_id resume works for custom state keys.
    assert result2["spike_value"] == "alpha|beta"
    assert isinstance(result2["structured_response"], SpikePlan)
    assert result2["structured_response"].title == "Spike Trip 2"

    # A different thread_id starts fresh (no leaked state) -> isolation.
    fresh = agent.invoke(
        {"messages": [("user", "remember gamma")]},
        config={"configurable": {"thread_id": "spike-thread-2"}},
    )
    assert fresh["spike_value"] == "gamma"
    assert fresh["spike_value"] != "alpha|beta"
