# Travel Assistant Agent — Design Document

- **Date:** 2026-05-18
- **Status:** Approved design (pre-implementation)
- **Architecture choice:** Option A — `create_agent` core + thin orchestration wrapper

## 1. Goal

Build an engineering-grade AI travel-planning agent in Python using LangChain 1.0
(`create_agent`) + LangGraph. The deliverable is a clean, GitHub-ready, interview-demonstrable
CLI travel assistant.

Given a request such as:

> "I want to travel from Shanghai to Tokyo for 5 days in June. My budget is comfort level.
> I like food and city walks."

the assistant asks focused clarifying questions when critical info is missing, calls mock
domain tools, produces a **structured itinerary**, estimates a budget, suggests
hotels/transportation, and can persist user travel preferences across sessions.

This is **not** a toy chatbot: it exercises `create_agent`, `ToolRuntime`, `Command`,
`ToolMessage`, checkpointer + `thread_id` short-term memory, a JSON long-term preference
store, Pydantic structured output, event streaming, and optional LangSmith tracing — all
under standard engineering hygiene (typing, tests, lint, CI).

### Non-goals (v1)

- Real flight/hotel/weather APIs (mock data only in v1).
- Automatic post-model preference extraction (v2 — see §10).
- LangGraph `BaseStore`-backed long-term memory (v2 — interface kept compatible).
- Web/GUI front end (CLI only).
- Hand-authored `StateGraph` (Option B is an explicit v2 path).

## 2. Tech baseline

- **Python 3.11+**, `src/` layout, packaged via `pyproject.toml`.
- **LangChain 1.0** (`langchain.agents.create_agent`) + **LangGraph** runtime.
  Exact versions are **pinned** in `pyproject.toml`; import paths/signatures are verified
  by an early spike (see §13 Risks).
- **CLI framework:** `typer` (testable via `typer.testing.CliRunner`).
- **Model:** `langchain.chat_models.init_chat_model`, default `deepseek:deepseek-chat`
  (`langchain-deepseek`, `DEEPSEEK_API_KEY`), swappable via env var.
- **FakeChatModel:** explicit, deterministic, network-free model for tests/CI and opt-in
  local runs (see §6).
- **Config:** `pydantic-settings` reading `.env`.
- **Quality:** `ruff` + `mypy` + `pytest`, `pre-commit`, `Makefile`, GitHub Actions CI
  (lint/type/test run **without** any API key).

## 3. Architecture

`create_agent` is the reasoning/tool-calling engine (it compiles to a LangGraph graph).
A thin wrapper assembles tools, prompt, structured output, memory, and the CLI.

- **Tools** declare a `ToolRuntime` parameter to read `state` / `context` / `store`.
  State-mutating tools return `Command(update={...})` plus a `ToolMessage`.
- **Structured output:** `response_format=TripPlan` (Pydantic) by default — no hard-coded
  output strategy. The final plan lands in `result["structured_response"]`. A fallback
  path (`ToolStrategy` or explicit JSON validation) is documented in §8, implemented only
  if DeepSeek structured output proves unstable.
- **Short-term memory:** checkpointer factory selected by `CHECKPOINTER_BACKEND`
  (`memory` default → `InMemorySaver`; `sqlite` → `SqliteSaver`) + `thread_id`. Enables
  multi-turn clarification and (with sqlite) resume across process restarts.
- **Long-term memory:** a `PreferenceStore` Protocol with a JSON implementation keyed by
  `user_id`. Preferences are loaded by the runner **before each run** and injected into
  state/context. They are persisted **only** via an explicit `save_preference` tool. No
  automatic extraction in v1. The Protocol is designed to be swapped for LangGraph
  `BaseStore` later (documented in `memory/UPGRADE.md`).
- **Clarification:** turn-based and flexible (see §5).

### 3.1 Project structure

```
travel-assistant/
├── README.md  pyproject.toml  .env.example  .gitignore  Makefile
├── .github/workflows/ci.yml
├── src/travel_assistant/
│   ├── __init__.py
│   ├── config.py            # pydantic-settings: keys, model id, CHECKPOINTER_BACKEND,
│   │                        #   TRAVEL_AGENT_FAKE_MODEL, langsmith toggle
│   ├── models.py            # TripRequest, TripPlan(+DayPlan/Activity/BudgetBreakdown),
│   │                        #   UserPreferences, tool I/O schemas
│   ├── state.py             # agent state schema (extends AgentState)
│   ├── llm.py               # init_chat_model wrapper + FakeChatModel + retry
│   ├── prompts.py           # system prompt(s), clarification policy text
│   ├── checkpointer.py      # backend factory (memory | sqlite)
│   ├── agent.py             # create_agent assembly (tools, response_format, checkpointer)
│   ├── runner.py            # load prefs → build context/state → invoke/stream agent
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── repository.py    # PreferenceStore Protocol
│   │   ├── json_store.py    # JSON impl, keyed by user_id
│   │   └── UPGRADE.md       # path to LangGraph BaseStore (v2)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── flights.py  hotels.py  weather.py  attractions.py  budget.py
│   │   ├── intake.py        # record_trip_request (Command state update)
│   │   ├── preferences.py   # save_preference (explicit persistence)
│   │   └── mock_data/       # deterministic fixtures
│   ├── streaming.py         # render stream events for the CLI
│   └── cli.py               # entrypoint: user_id/thread_id/--new/--fake, multi-turn loop
├── tests/
│   ├── conftest.py
│   ├── test_models.py  test_tools_*.py  test_memory.py
│   ├── test_agent_smoke.py  test_short_term_memory.py  test_cli.py
└── docs/superpowers/specs/2026-05-18-travel-assistant-agent-design.md
```

## 4. Core data models (Pydantic)

- **`TripRequest`** — `origin`, `destination`, `start_date`/`end_date` or `duration_days`,
  `party_size`, `comfort_level` (`budget|comfort|luxury`), `interests: list[str]`.
  A `missing_critical_fields()` helper returns which required fields are absent; this
  drives clarification. **Critical fields:** origin, destination, dates-or-duration,
  comfort_level. `interests` and `party_size` are non-critical (sensible defaults).
- **`TripPlan`** — `summary`, `days: list[DayPlan]` (each: date, `weather`,
  ordered `activities: list[Activity]`), `flight_options: list[FlightOption]`,
  `hotel_options: list[HotelOption]`, `transport_notes`, `budget: BudgetBreakdown`,
  `assumptions: list[str]` (records any defaulted/inferred values).
- **`UserPreferences`** — `user_id`, `liked_interests`, `preferred_comfort_level`,
  `pace_notes`, `dietary_notes`, `home_city`. Merged into context each session.
- **Tool I/O schemas** — explicit request/response models per tool for typed validation.

## 5. Clarification behavior

Turn-based, flexible, bounded:

- Compute `TripRequest.missing_critical_fields()` from the conversation so far.
- **Exactly one** critical field missing → ask **one** focused question.
- **Multiple** critical fields missing → ask **up to 2–3** focused questions in a single
  turn (never an open-ended interview).
- After asking, the turn ends; the CLI loops the user's reply under the same `thread_id`;
  the checkpointer preserves history.
- **Loop bound:** at most **2 clarification rounds**. If critical fields are still missing
  after round 2, proceed with sensible defaults and record each in `TripPlan.assumptions`.
- **Required test case:** when *only* budget/comfort is missing, the agent asks **only**
  about budget — no other questions.

The clarification policy lives in `prompts.py` and is enforced by prompt instructions plus
the deterministic `missing_critical_fields()` signal injected into state.

## 6. Model selection & FakeChatModel policy

`llm.py` resolves the model with this precedence:

1. `--fake` CLI flag or `TRAVEL_AGENT_FAKE_MODEL=true` → **FakeChatModel** (explicit).
2. Test/CI: the pytest `conftest.py` and CI workflow set
   `TRAVEL_AGENT_FAKE_MODEL=true` explicitly (no runtime pytest sniffing) so the fake
   model is the default there via rule 1.
3. Otherwise (normal CLI run) → real `init_chat_model(settings.model_id)`:
   - If `DEEPSEEK_API_KEY` is **missing**, raise a **clear error** instructing the user to
     set the key or pass `--fake`. **No silent fallback** — we never let a run appear to
     use DeepSeek while secretly using a fake model.
4. On real-model selection the CLI prints which model is active; on fake mode it prints a
   conspicuous `*** FAKE MODEL ***` banner.

FakeChatModel is deterministic and scriptable so component/CLI tests can drive multi-turn
clarify→plan flows without network access.

## 7. Data flow (one session)

1. CLI parses `user_id`, `thread_id` (`--new` starts fresh), `--fake`.
2. `runner.py` loads `UserPreferences` from the JSON store (empty if none) and injects
   them into context/state.
3. `checkpointer.py` builds the configured backend; `agent.py` assembles `create_agent`.
4. User message → agent. If critical `TripRequest` fields are missing, agent asks
   1–3 focused questions per §5; turn ends; CLI loops on same `thread_id`.
5. When complete (or after the round bound), `record_trip_request` writes `TripRequest`
   to state via `Command` + `ToolMessage`.
6. Domain tools (`search_flights/hotels`, `get_weather`, `find_attractions`) read
   `TripRequest`/prefs from state via `ToolRuntime`; `estimate_budget` consumes the
   gathered data.
7. Agent returns `TripPlan` via `response_format` → `structured_response`.
8. If the user expressed a durable preference, the agent calls `save_preference`
   (explicit) → JSON store.
9. `streaming.py` renders agent steps live; CLI pretty-prints the final `TripPlan` +
   budget.

## 8. Structured output & fallback

- **Default:** `create_agent(..., response_format=TripPlan)`; read
  `result["structured_response"]`.
- **Documented fallback (not implemented unless needed):** if DeepSeek structured output
  is unstable, switch to `ToolStrategy(TripPlan)` or add an explicit
  `TripPlan.model_validate_json` parse-and-retry step. Final validation failure path:
  retry once → fallback strategy → best-effort text plus an error note appended to
  `TripPlan.assumptions`.

## 9. Milestones

Each milestone ends with a concrete acceptance check.

| # | Milestone | Acceptance criteria |
|---|-----------|---------------------|
| **M0** | Scaffold: layout, `pyproject`, `config.py` (keys, model id, `CHECKPOINTER_BACKEND`, `TRAVEL_AGENT_FAKE_MODEL`, langsmith), `.env.example`, `.gitignore`, `Makefile`, CI, README skeleton | `make install`; `make lint type test` green (placeholder tests); `python -m travel_assistant --help` works |
| **M1** | Domain models: `TripRequest` (+`missing_critical_fields`), `TripPlan` (+sub-models), `UserPreferences`, tool I/O schemas | Model unit tests pass; completeness logic tested (which fields block planning) |
| **M2** | Mock tools: `search_flights/hotels`, `get_weather`, `find_attractions`, `estimate_budget`, `record_trip_request`, `save_preference`; deterministic fixtures | Per-tool unit tests pass; outputs deterministic for a fixed seed |
| **M3** | Memory: JSON `PreferenceStore` (Protocol + impl) keyed by `user_id`; `UPGRADE.md` | Roundtrip + keyed-by-user + corrupt-file-recovery tests pass |
| **M4** | LLM layer: `init_chat_model` wrapper (default `deepseek:deepseek-chat`) + `FakeChatModel` + retry + selection-precedence (§6) | No key + normal run → clear error; `--fake`/`TRAVEL_AGENT_FAKE_MODEL` → fake; pytest → fake by default |
| **M5** | Agent core: `state.py`, system prompt + clarification policy, `create_agent` assembly with tools + `response_format=TripPlan`; prefs injected by `runner.py` | Smoke test (FakeChatModel) yields valid `structured_response`; prefs visible in prompt/context |
| **M6** | `ToolRuntime` + `Command`/state: intake tool writes `TripRequest` via `Command`; domain tools read state/context via `ToolRuntime`; `save_preference` persists | State-update & `ToolRuntime`-read unit tests pass |
| **M7** | Short-term memory + clarification: `checkpointer.py` factory (memory default / sqlite when configured) + `thread_id`; flexible clarify loop (§5) | Only-budget-missing → asks only about budget; multi-field-missing → ≤3 questions; ≤2 rounds then proceed with assumptions; sqlite resume-after-restart test (gated, tmp db) passes |
| **M8** | Streaming + CLI UX: stream rendering, multi-turn loop, args (`user_id`/`thread_id`/`--new`/`--fake`), fake-mode banner, pretty `TripPlan` + budget output | CLI test with scripted multi-turn input + FakeChatModel passes; manual run with real DeepSeek key on the sample prompt produces a valid plan |
| **M9** | LangSmith (optional) + polish: env-gated tracing, README (architecture diagram, run guide, structured-output fallback, v2 roadmap) | Tracing toggles via env only (no code change); full `make ci` green; docs complete |

## 10. Error handling

- **Startup/config:** missing/invalid env → clear message; normal run without
  `DEEPSEEK_API_KEY` and no `--fake` → **explicit error** (no silent fallback); invalid
  `CHECKPOINTER_BACKEND` → error listing valid values.
- **Tool errors:** tools return typed error payloads; `ToolNode` error handling feeds an
  error `ToolMessage` back so the agent recovers or reports — the loop never crashes.
- **Validation:** bad tool input → recoverable `ToolMessage`; final `TripPlan` validation
  failure → retry once → documented fallback (§8) → best-effort text + error note in
  `assumptions`.
- **Model/network:** `tenacity` retry with backoff on transient DeepSeek errors; friendly
  CLI message + non-zero exit on hard failure.
- **Persistence:** unwritable sqlite path → log + fall back to memory checkpointer with a
  warning; missing/corrupt prefs JSON → treated as empty, bad file backed up.
- **CLI:** empty input ignored; Ctrl-C exits gracefully; unknown `thread_id` → fresh start
  with notice; `--new` over an existing thread → confirm.

## 11. Testing strategy

- **Unit:** models (incl. `missing_critical_fields`), each mock tool (deterministic by
  seed), `PreferenceStore` (roundtrip / keyed-by-user / corrupt-file recovery).
- **Component:** agent smoke with `FakeChatModel` — graph wiring, tool calls,
  `structured_response` shape, `ToolRuntime` reads, `Command` updates, `save_preference`
  persistence, prefs injection.
- **Short-term memory:** multi-turn clarify→plan (FakeChatModel) including the
  only-budget-missing case and the multi-field case; sqlite resume-after-restart
  (marked, tmp db).
- **CLI:** `typer` `CliRunner`/subprocess with scripted input + FakeChatModel; asserts
  pretty output, fake-mode banner, and valid plan.
- **Integration (optional):** marked `integration`, auto-skipped without
  `DEEPSEEK_API_KEY`; real DeepSeek run on the sample prompt asserts a valid `TripPlan`
  + budget.
- **Gates:** `ruff` + `mypy` + `pytest` in CI with **no API keys**; ~80% coverage on core
  (tools/models/memory/state).

## 12. v1 Definition of Done

- Sample prompt (*Shanghai→Tokyo, 5 days in June, comfort, food + city walks*) → valid
  `TripPlan`: budget, ≥1 flight & hotel option, per-day activities matching interests,
  `assumptions` listing any defaulted fields.
- Only-budget-missing → exactly one clarifying question (budget), then a plan on the same
  thread; multi-field-missing → ≤3 questions; clarification bounded to ≤2 rounds.
- `save_preference` then a new session for the same `user_id` reflects saved prefs.
- Normal run without a key and without `--fake` errors clearly; `--fake`/CI uses
  FakeChatModel with a conspicuous banner; real DeepSeek used when a key is present.
- `make ci` green; README covers architecture, setup, structured-output fallback, and the
  v2 roadmap.

## 13. Implementation risks & mitigations

- **LangChain 1.0 / LangGraph API drift (highest risk).** `create_agent`,
  `ToolRuntime`, `Command`, `response_format`/`structured_response`, and the sqlite
  checkpointer (`langgraph-checkpoint-sqlite`) / `langchain-deepseek` packages have
  version-sensitive import paths and signatures.
  **Mitigation:** pin all versions in `pyproject.toml`; the **first plan step is a
  throwaway spike** that wires `create_agent` + a `ToolRuntime` tool + a `Command` state
  update + `response_format` against `FakeChatModel` and asserts the result shape. Build
  domain logic only after the spike passes. M0 acceptance includes an import smoke.
- **Scripted `FakeChatModel` is real work.** Driving clarify→`record_trip_request`→
  domain tools→structured output requires a deterministic model that emits a scripted
  sequence of `AIMessage`s with the correct `tool_calls`.
  **Mitigation:** treat it as a first-class test fixture (queue/scripted responses, built
  on `langchain_core` fake-model primitives); deliver it in M4 and reuse everywhere.
- **DeepSeek structured output stability.** Covered by the §8 fallback (`ToolStrategy` /
  explicit JSON validation), implemented only if instability is observed.

## 14. v2 roadmap (out of scope for v1)

- Automatic post-model preference extraction via agent middleware.
- LangGraph `BaseStore`-backed long-term memory (swap behind `PreferenceStore` Protocol).
- Real provider integrations behind the mock tool interfaces.
- Optional hand-authored `StateGraph` (Option B) for deeper LangGraph demonstration.
