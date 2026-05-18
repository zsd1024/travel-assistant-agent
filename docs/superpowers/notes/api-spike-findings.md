# API Compatibility Spike — Findings (AUTHORITATIVE)

Task 2 output. Every fact below was **verified empirically** against the
pinned, installed versions by running real code and reading installed
package source under `.venv/lib/python3.11/site-packages/`. Where this
document and the original DESIGN/PLAN disagree, **later tasks (M5/M6) MUST
follow this document**, not the plan.

Spike that proves all of this: `tests/spikes/test_langchain_api_spike.py`
(kept intentionally — not throwaway). Run:

```
.venv/bin/python -m pytest tests/spikes/ -v
```

## Verified versions

| Package | Version |
|---|---|
| langchain | 1.3.1 |
| langchain-core | 1.4.0 |
| langgraph | 1.2.0 |
| langgraph-checkpoint | 4.1.0 |
| langgraph-checkpoint-sqlite | 2.0.10 |
| langgraph-prebuilt | 1.1.0 |
| langchain-deepseek | 1.0.1 |
| pydantic | 2.13.4 |

## Confirmed import paths

```python
from langchain.agents import create_agent          # module: langchain.agents.factory
from langchain.agents import AgentState             # module: langchain.agents.middleware.types
from langchain.tools import ToolRuntime             # impl: langgraph.prebuilt.tool_node.ToolRuntime
from langgraph.types import Command
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
```

## `create_agent`

Signature observed via `inspect.signature` on the installed package; the kwargs
used below are additionally execution-verified by the spike (the spike itself
does not call `inspect`):

```
create_agent(
    model: str | BaseChatModel,
    tools: Sequence[BaseTool | Callable | dict] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    response_format: ResponseFormat | type | dict | None = None,
    state_schema: type[AgentState] | None = None,
    context_schema: type | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
    transformers: Sequence[Callable] | None = None,
) -> CompiledStateGraph
```

- All plan-assumed kwargs **exist and are accepted**: `model`, `tools`,
  `system_prompt`, `response_format`, `checkpointer`, `state_schema`,
  `context_schema`.
- `system_prompt` is keyword-only and accepts `str | SystemMessage`.
- `tools` is the **second positional** arg (positional or keyword).
- Returns a `CompiledStateGraph`; `.invoke(input, config=...)` is the entrypoint.

## Agent-state base class (drives M5 `state.py`)

- The real base is **`langchain.agents.AgentState`** (re-exported from
  `langchain.agents.middleware.types`). It is a `Generic` `dict` subclass
  (TypedDict-style; MRO `AgentState -> Generic -> dict -> object`).
- Built-in keys: `messages`
  (`Required[Annotated[list[AnyMessage], add_messages]]`), `jump_to`
  (ephemeral/private), `structured_response`
  (`NotRequired[Annotated[ResponseT, OmitFromInput]]`).
- **Extension pattern (verified working):** subclass it and add keys:

  ```python
  from langchain.agents import AgentState

  class SpikeState(AgentState):
      spike_value: str | None
  ```

  Pass it as `state_schema=SpikeState` to `create_agent`. Custom keys are
  readable via `runtime.state[...]`, settable via `Command(update=...)`, and
  **persisted by the checkpointer** across invokes on the same `thread_id`.

## `ToolRuntime` (drives every M6 tool)

- Import: `from langchain.tools import ToolRuntime`. Implementation lives at
  `langgraph.prebuilt.tool_node.ToolRuntime` (also importable from
  `langgraph.prebuilt`; `langchain.tools` is the canonical LangChain path).
- It is a `@dataclass` with fields: `state`, `context`, `config`,
  `stream_writer`, `tool_call_id`, `store`, `tools`, `execution_info`,
  `server_info`.
- **Declaration: NO `Annotated` wrapper.** A tool just declares a parameter
  named `runtime` typed `ToolRuntime`; the tool-execution system
  auto-injects it:

  ```python
  def remember(text: str, runtime: ToolRuntime) -> Command:
      prior = runtime.state.get("spike_value")  # custom state key
      cid   = runtime.tool_call_id              # current tool-call id (str)
      # runtime.context / runtime.store / runtime.config also available
      ...
  ```

- `runtime.state` is the **current (custom) state dict** — `state["messages"]`
  and any custom keys (e.g. `spike_value`) are present.
- `runtime.tool_call_id` is the id needed to construct a correlated
  `ToolMessage`.

## `Command` — state update + ToolMessage append

- Import: `from langgraph.types import Command` (NOT a class with the
  ToolMessage merged automatically — you append it yourself).
- Constructor (verified): `Command(*, graph=None, update=None, resume=None,
  goto=())`.
- A tool returns a `Command` whose `update` dict both sets custom state keys
  and appends to `messages` (which is reduced by `add_messages`):

  ```python
  return Command(update={
      "spike_value": new_value,
      "messages": [ToolMessage(content="...", tool_call_id=runtime.tool_call_id)],
  })
  ```

- The `ToolMessage` ends up in `result["messages"]`. `add_messages` merges
  the list rather than replacing it.

## `response_format` + structured output (drives M5 result handling)

- The structured result is found at **`result["structured_response"]`** (the
  plan's assumed key name is correct). It is an instance of the Pydantic
  model passed to `response_format`.
- A **raw** schema (`response_format=SpikePlan`) is wrapped internally as
  `AutoStrategy`. Auto-detection inspects the model:
  - If `model.profile` advertises `structured_output` (or the model name
    matches `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT` =
    `['grok','gpt-5','gpt-4.1','gpt-4o','gpt-oss','o3-pro','o3-mini']`),
    `ProviderStrategy` (native structured output) is used.
  - Otherwise it falls back to **`ToolStrategy`**: the model must emit a
    **tool call whose name is the Pydantic class name** (e.g. `"SpikePlan"`)
    with args matching the schema. The agent parses that tool call into
    `structured_response`, appends a synthetic
    `ToolMessage("Returning structured response: ...")`, and stops.
- **DeepSeek (real M5 model) — ⚠️ UNVERIFIED:** the spike makes **no live
  DeepSeek call** (not possible without an API key / network), so the
  production structured-output strategy is **not empirically known**.
  Counter-evidence to the earlier assumption: `'profile'` does not appear in
  `ChatDeepSeek`'s source, and `'deepseek'` is **not** in langchain's
  `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT`, so "DeepSeek → `ProviderStrategy`"
  is an unproven inference and may be wrong. **M5 MUST empirically
  detect/verify the structured-output strategy during DeepSeek integration**
  and **design for BOTH** paths — native `ProviderStrategy` *and* the
  `ToolStrategy` fallback (schema-named tool call). Do not hard-code either.
  The `ToolStrategy` path above is confirmed only for the profile-less fake
  model used in tests.

## Checkpointer + thread resume

- `from langgraph.checkpoint.memory import InMemorySaver` — pass as
  `checkpointer=InMemorySaver()` to `create_agent`.
- Thread is selected via
  `config={"configurable": {"thread_id": "<id>"}}` on `.invoke(...)`.
- **Verified resume behavior:** a second `invoke` on the **same** `thread_id`
  sees prior state — the spike's tool reads the prior `spike_value` from
  `runtime.state` and accumulates it (`"alpha"` then `"alpha|beta"`). A
  **different** `thread_id` starts fresh (`"gamma"`, not `"alpha|beta"`) —
  thread isolation confirmed.

### Checkpointer serialization caveat (IMPORTANT for M5/M6)

When a checkpointer persists a custom Pydantic model placed in state (e.g.
`structured_response` / a future `TripPlan`), langgraph-checkpoint 4.1.0 logs:

> `Deserializing unregistered type <module>.<Model> from checkpoint. This
> will be blocked in a future version. Set LANGGRAPH_STRICT_MSGPACK=true to
> block now, or add to allowed_msgpack_modules to allow explicitly: ...`

Today it is only a **logged warning** (not raised; not surfaced in pytest's
warnings summary because it goes through `logging`, not `warnings`). It will
become an error in a future langgraph. M5/M6 should plan to either register
allowed msgpack modules (`allowed_msgpack_modules=` on the serde /
checkpointer constructor) or otherwise account for this when persisting
Pydantic domain models with the SQLite checkpointer.

## Fake chat model for deterministic tests

- `from langchain_core.language_models.fake_chat_models import GenericFakeChatModel`.
- Construct with `GenericFakeChatModel(messages=<iterator of messages>)`. Its
  `_generate` does `next(self.messages)` per model call; non-`str` messages
  pass through unchanged, so scripted `AIMessage`s with `tool_calls` work.
- **CRITICAL DEVIATION:** `GenericFakeChatModel` (and every other
  `langchain_core` fake chat model) **does NOT implement `bind_tools`** — the
  base `BaseChatModel.bind_tools` raises `NotImplementedError`.
  `create_agent` **always calls `model.bind_tools(...)`** when tools and/or
  structured output are present. A deterministic fake MUST subclass it and
  override `bind_tools` to return `self` (binding is a no-op for a fake; the
  scripted messages already carry the tool calls). See `ScriptedFakeChatModel`
  in the spike. **M5/M6 test harness must use this subclass pattern, not bare
  `GenericFakeChatModel`.**
- **Verified model-loop shape:** one `invoke` doing a tool call then a
  structured response = **exactly 2 model calls** (call 1: domain tool call;
  call 2: schema-named tool call → structured output, then STOP — no extra
  model call after structured output). Scripted-message budget must match:
  N invokes that each do (tool-call → structured-output) need `2*N` scripted
  messages.

## Deviations from original design/plan

1. **`AgentState` import path is correct as `from langchain.agents import
   AgentState`** — it is genuinely exported there (re-exported from
   `langchain.agents.middleware.types`). No change needed, but the real
   module of record is `langchain.agents.middleware.types`.
2. **`ToolRuntime` import**: plan draft said
   `from langchain.tools import ToolRuntime  # adjust path`. Confirmed:
   `from langchain.tools import ToolRuntime` is correct (impl is
   `langgraph.prebuilt.tool_node.ToolRuntime`). **No `Annotated` wrapper** is
   used; the plan draft's unused `from typing import Annotated` is correctly
   omitted.
3. **`Command` import**: plan assumed `langgraph.types` — **correct**,
   confirmed `from langgraph.types import Command`.
4. **`ToolMessage` import**: plan assumed `langchain_core.messages` —
   **correct** (`langchain_core.messages.tool` underneath).
5. **`response_format` result key**: plan assumed
   `result["structured_response"]` — **correct**.
6. **Fake model `bind_tools` (NEW, not anticipated by the plan):** the plan's
   draft used a bare `GenericFakeChatModel`, which **fails** with
   `NotImplementedError` inside `create_agent` (it calls `bind_tools`). A
   `bind_tools`-returning-`self` subclass is **required**. This is the single
   biggest correction; M5/M6 test infrastructure depends on it.
7. **Structured-output requires a schema-named tool call for profile-less
   models (NEW):** the plan's draft scripted a final
   `AIMessage(content='{"title": "Trip"}')` (raw JSON content). With the
   `ToolStrategy` fallback that does **not** produce a `structured_response`;
   the model must emit a tool call **named after the Pydantic class** with
   matching args. Plan draft's final assistant message shape is wrong for the
   fake-model path.
8. **Model-call budget / loop shape (NEW):** one tool-call + structured
   response = exactly 2 model calls; scripts must be sized `2*invokes`.
   Plan's draft scripted only 2 messages for a single invoke that also
   expected a `ToolMessage` — workable count-wise, but the *content* of msg 2
   was wrong (see #7).
9. **Checkpointer msgpack deserialization warning (NEW):** persisting custom
   Pydantic models via the checkpointer logs an "unregistered type" warning
   that will become a hard error in a future langgraph. M5/M6 must plan for
   `allowed_msgpack_modules` / `LANGGRAPH_STRICT_MSGPACK` handling.
10. **DeepSeek structured-output strategy (NEW) — ⚠️ UNVERIFIED:** the spike
    makes no live DeepSeek call, so whether real DeepSeek uses
    `ProviderStrategy` (native) or the `ToolStrategy` fallback is **not
    verified** (`'profile'` absent from `ChatDeepSeek` source; `'deepseek'`
    not in `FALLBACK_MODELS_WITH_STRUCTURED_OUTPUT`). M5 must **empirically
    detect/verify the strategy during integration** and **support BOTH**
    `ProviderStrategy` and the `ToolStrategy` fallback. The schema-named
    tool-call behavior is confirmed only for profile-less fakes in tests.

## Quality gate (all green at time of writing)

```
make lint   -> ruff check src tests : All checks passed!
make type   -> mypy : Success: no issues found in 3 source files
pytest -q   -> 4 passed (3 M0 smoke + 1 spike)
pytest tests/spikes/ -v -> 1 passed
```
