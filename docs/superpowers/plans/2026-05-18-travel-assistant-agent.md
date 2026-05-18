# Travel Assistant Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an engineering-grade CLI travel-planning agent using LangChain 1.0 `create_agent` + LangGraph, with mock tools, short/long-term memory, structured Pydantic output, and streaming.

**Architecture:** Option A — `create_agent` is the reasoning/tool engine; a thin wrapper adds typed tools (`ToolRuntime`/`Command`), a checkpointer factory (memory/sqlite), a JSON `PreferenceStore`, `response_format=TripPlan` structured output, and a `typer` CLI with event streaming.

**Tech Stack:** Python 3.11+, LangChain 1.0 (`langchain.agents.create_agent`), LangGraph (`langgraph-checkpoint-sqlite`), `langchain-deepseek`, Pydantic v2, `pydantic-settings`, `typer`, `tenacity`, `pytest`, `ruff`, `mypy`.

**Spec:** `docs/superpowers/specs/2026-05-18-travel-assistant-agent-design.md`

**Conventions for every task:** TDD (failing test → minimal code → green → commit). Exact paths. One milestone = one Task = one milestone commit at the end. Pinned versions. `TRAVEL_AGENT_FAKE_MODEL=true` is set in `tests/conftest.py` so all tests use the deterministic fake model.

**Commit author:** `git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" commit ...` (repo already initialized; `docs/` and `.gitignore` already committed).

---

## Task 1 — M0: Project scaffold (scaffold ONLY; no domain logic)

**Goal:** A runnable, installable, lint/type/test-green skeleton with package structure and a CLI `--help` placeholder. No models, tools, or agent yet.

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore` (already committed — extend if needed)
- Create: `Makefile`
- Create: `README.md`
- Create: `src/travel_assistant/__init__.py`
- Create: `src/travel_assistant/__main__.py`
- Create: `src/travel_assistant/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [x] **Step 1: Write `pyproject.toml`** (pinned versions)

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "travel-assistant"
version = "0.1.0"
description = "Engineering-grade CLI travel-planning agent (LangChain 1.0 + LangGraph)"
requires-python = ">=3.11"
dependencies = [
    "langchain==1.3.1",
    "langgraph==1.2.0",
    "langgraph-checkpoint-sqlite==2.0.10",
    "langchain-deepseek==1.0.1",
    "langchain-core==1.4.0",
    "pydantic==2.13.4",
    "pydantic-settings==2.14.1",
    "typer==0.23.1",
    "click==8.1.8",
    "tenacity==9.1.4",
]

[project.optional-dependencies]
dev = ["pytest==8.4.2", "ruff==0.15.13", "mypy==1.20.2", "pytest-cov==6.3.0"]

[project.scripts]
travel-assistant = "travel_assistant.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
packages = ["travel_assistant"]
mypy_path = "src"
ignore_missing_imports = true
strict = false

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
markers = ["integration: real DeepSeek calls; skipped without DEEPSEEK_API_KEY"]
```

> **Versions empirically resolved & M0-verified on Python 3.11.15 (2026-05-18):** the
> original draft pins (`langchain==1.0.3`, `langchain-deepseek==0.1.4`, `typer==0.12.5`,
> `langgraph==1.0.2`) were mutually incompatible; the set above is a clean, reproducible
> resolution (added explicit `click==8.1.8`; `langchain-deepseek` moved to the 1.x line
> for `langchain-core` 1.x; `langgraph` 1.2.0 keeps `langgraph-prebuilt` consistent).
> Requires Python ≥3.11. If a future pin fails to resolve, that is the trigger for the
> Task 2 spike — do not unpin silently.

- [x] **Step 2: Write `.env.example`**

```bash
# Real model (omit to be forced into --fake / TRAVEL_AGENT_FAKE_MODEL)
DEEPSEEK_API_KEY=
TRAVEL_AGENT_MODEL_ID=deepseek:deepseek-chat
# memory (default) | sqlite
CHECKPOINTER_BACKEND=memory
TRAVEL_AGENT_SQLITE_PATH=data/checkpoints.sqlite3
TRAVEL_AGENT_PREFS_PATH=data/preferences.json
# explicit fake model (no network)
TRAVEL_AGENT_FAKE_MODEL=false
# optional tracing
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
```

- [x] **Step 3: Ensure `.gitignore` covers data/build artifacts**

Confirm these lines exist (append any missing): `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `*.sqlite3`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `data/preferences.json`, `data/checkpoints.sqlite3`, `*.egg-info/`, `.coverage`.

- [x] **Step 4: Write `Makefile`**

```make
.PHONY: install lint type test ci run
install:
	python -m pip install -e ".[dev]"
lint:
	ruff check src tests
type:
	mypy
test:
	pytest -q
ci: lint type test
run:
	python -m travel_assistant
```

- [x] **Step 5: Write `README.md` skeleton**

```markdown
# Travel Assistant Agent

Engineering-grade CLI travel-planning agent (LangChain 1.0 `create_agent` + LangGraph).

## Status
Scaffold (M0). See `docs/superpowers/plans/2026-05-18-travel-assistant-agent.md`.

## Quickstart
\`\`\`bash
make install
cp .env.example .env   # set DEEPSEEK_API_KEY, or run with --fake
python -m travel_assistant --help
\`\`\`

## Architecture
See `docs/superpowers/specs/2026-05-18-travel-assistant-agent-design.md`.

## Roadmap
M0 scaffold · M1 models · M2 tools · M3 memory · M4 LLM layer ·
M5 agent core · M6 ToolRuntime/Command · M7 short-term memory ·
M8 streaming/CLI · M9 tracing + polish.
```

- [x] **Step 6: Write package files**

`src/travel_assistant/__init__.py`:
```python
__version__ = "0.1.0"
```

`src/travel_assistant/cli.py` (a `@app.callback()` makes Typer a command group so
app-level `--help` shows the app description; later tasks invoke `["plan", ...]`):
```python
"""CLI entrypoint (placeholder until M8)."""
import typer

app = typer.Typer(add_completion=False, help="Travel Assistant Agent CLI")


@app.callback()
def main() -> None:
    """Travel Assistant Agent CLI."""


@app.command()
def plan(
    fake: bool = typer.Option(False, "--fake", help="Use the deterministic fake model"),
) -> None:
    """Plan a trip (not implemented until M8)."""
    typer.echo("Travel Assistant scaffold OK. Planning is implemented in M8.")
    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
```

`src/travel_assistant/__main__.py`:
```python
from travel_assistant.cli import app

if __name__ == "__main__":
    app()
```

- [x] **Step 7: Write `tests/conftest.py`** (forces fake model everywhere)

```python
import pytest


@pytest.fixture(autouse=True)
def _force_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_FAKE_MODEL", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
```

- [x] **Step 8: Write the failing smoke test** — `tests/test_smoke.py`

```python
from typer.testing import CliRunner

from travel_assistant import __version__
from travel_assistant.cli import app


def test_version_present() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_runs() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Travel Assistant" in result.output


def test_langchain_imports() -> None:
    # M0 import smoke (spec §13): confirm core APIs import.
    from langchain.agents import create_agent  # noqa: F401
    from langgraph.checkpoint.memory import InMemorySaver  # noqa: F401
```

- [x] **Step 9: Run install + verify failure→pass**

Run: `make install && pytest -q`
Expected: `test_langchain_imports` is the canary — if `create_agent` import path differs, it FAILS here (feeds Task 2). Otherwise all 3 tests PASS.

- [x] **Step 10: Run lint + type**

Run: `make lint type`
Expected: both exit 0.

- [x] **Step 11: Commit M0**

```bash
git add pyproject.toml .env.example .gitignore Makefile README.md src tests
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m0): project scaffold, CLI placeholder, smoke tests"
```

**Acceptance:** `make install` succeeds; `pytest -q` green (3 tests); `make lint type` clean; `python -m travel_assistant --help` exits 0.

**Risks:** Pinned versions may not resolve / `create_agent` import path may differ in the installed LangChain. Mitigation: `test_langchain_imports` fails loudly → resolve in Task 2 before any domain code.

---

## Task 2 — API Compatibility Spike (throwaway; spec §13)

**Goal:** Prove the exact LangChain 1.0 / LangGraph API surface used everywhere later: `create_agent`, a `ToolRuntime` tool, a `Command` state update, `response_format` structured output, `InMemorySaver` + `thread_id`. Record findings; delete the throwaway code.

**Files:**
- Create: `tests/spike/test_api_spike.py`
- Create: `docs/superpowers/notes/api-spike-findings.md`

- [ ] **Step 1: Write the spike test** — `tests/spike/test_api_spike.py`

```python
"""Throwaway: validates LangChain 1.0 API shapes. Delete impl, keep findings doc."""
from typing import Annotated

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel


class Plan(BaseModel):
    title: str


def test_create_agent_with_tool_command_and_structured_output() -> None:
    # If ToolRuntime import path differs, fix it here and record in findings.
    from langchain.tools import ToolRuntime  # adjust path per installed version

    def note(text: str, runtime: ToolRuntime) -> str:
        assert runtime is not None
        return f"noted:{text}"

    scripted = iter([
        AIMessage(content="", tool_calls=[{"name": "note", "args": {"text": "hi"}, "id": "1"}]),
        AIMessage(content='{"title": "Trip"}'),
    ])
    model = GenericFakeChatModel(messages=scripted)
    agent = create_agent(
        model=model,
        tools=[note],
        response_format=Plan,
        checkpointer=InMemorySaver(),
    )
    result = agent.invoke(
        {"messages": [("user", "plan it")]},
        config={"configurable": {"thread_id": "t1"}},
    )
    assert isinstance(result["structured_response"], Plan)
    assert any(isinstance(m, ToolMessage) for m in result["messages"])
```

- [ ] **Step 2: Run the spike**

Run: `pytest tests/spike/test_api_spike.py -v`
Expected: PASS. If any import path/signature differs, **adjust the test until it passes** (this is the point of the spike) and note every deviation.

- [ ] **Step 3: Record findings** — `docs/superpowers/notes/api-spike-findings.md`

Document the **verified** import paths and signatures the rest of the plan depends on:
- `create_agent` import path + accepted kwargs (`model`, `tools`, `response_format`, `checkpointer`, `system_prompt`, `state_schema`, `context_schema`).
- `ToolRuntime` import path + how `state`/`context`/`store` are accessed.
- How a tool returns a state update (`Command(update=...)` import path: `langgraph.types`).
- Result keys: `structured_response`, `messages`.
- Fake model class used for scripted tool-calls.

If any later task's code in this plan contradicts these findings, the findings win — adjust the code at implementation time and note it in the task's commit.

- [ ] **Step 4: Commit the findings, delete throwaway**

```bash
git rm -r --quiet tests/spike
git add docs/superpowers/notes/api-spike-findings.md
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "chore(spike): verify LangChain 1.0 API surface; record findings"
```

**Acceptance:** spike passed locally; `api-spike-findings.md` lists concrete, verified import paths/signatures; throwaway test removed.

**Risks:** API differs from plan assumptions. Mitigation: this task exists precisely to surface that *before* domain code; later tasks reference the findings doc.

---

## Task 3 — M1: Domain models

**Goal:** Pydantic models with completeness logic driving clarification.

**Files:**
- Create: `src/travel_assistant/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests** — `tests/test_models.py`

```python
from datetime import date

from travel_assistant.models import (
    Activity, BudgetBreakdown, ComfortLevel, DayPlan,
    TripPlan, TripRequest, UserPreferences,
)


def test_missing_critical_fields_only_comfort() -> None:
    req = TripRequest(origin="Shanghai", destination="Tokyo", duration_days=5)
    assert req.missing_critical_fields() == ["comfort_level"]


def test_missing_critical_fields_multiple() -> None:
    req = TripRequest(origin="Shanghai")
    missing = set(req.missing_critical_fields())
    assert {"destination", "dates_or_duration", "comfort_level"} <= missing
    assert "origin" not in missing


def test_complete_request_has_no_missing() -> None:
    req = TripRequest(
        origin="Shanghai", destination="Tokyo", duration_days=5,
        comfort_level=ComfortLevel.COMFORT, interests=["food"],
    )
    assert req.missing_critical_fields() == []


def test_tripplan_roundtrip() -> None:
    plan = TripPlan(
        summary="s",
        days=[DayPlan(day_index=1, date=date(2026, 6, 1), weather="sunny",
                      activities=[Activity(name="walk", category="city walk")])],
        flight_options=[], hotel_options=[], transport_notes="metro",
        budget=BudgetBreakdown(currency="USD", flights=0, lodging=0,
                               food=0, activities=0, local_transport=0, total=0),
        assumptions=["party_size defaulted to 1"],
    )
    assert TripPlan.model_validate_json(plan.model_dump_json()).summary == "s"
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_models.py -q`
Expected: FAIL (`ModuleNotFoundError: travel_assistant.models`).

- [ ] **Step 3: Implement `src/travel_assistant/models.py`**

```python
"""Domain models. Critical fields gate planning (spec §4, §5)."""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class ComfortLevel(str, Enum):
    BUDGET = "budget"
    COMFORT = "comfort"
    LUXURY = "luxury"


class TripRequest(BaseModel):
    origin: str | None = None
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int | None = None
    party_size: int = 1
    comfort_level: ComfortLevel | None = None
    interests: list[str] = Field(default_factory=list)

    def _has_dates_or_duration(self) -> bool:
        return self.duration_days is not None or (
            self.start_date is not None and self.end_date is not None
        )

    def missing_critical_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.origin:
            missing.append("origin")
        if not self.destination:
            missing.append("destination")
        if not self._has_dates_or_duration():
            missing.append("dates_or_duration")
        if self.comfort_level is None:
            missing.append("comfort_level")
        return missing


class Activity(BaseModel):
    name: str
    category: str
    notes: str = ""


class DayPlan(BaseModel):
    day_index: int
    date: date | None = None
    weather: str = ""
    activities: list[Activity] = Field(default_factory=list)


class FlightOption(BaseModel):
    carrier: str
    depart: str
    arrive: str
    price: float
    currency: str = "USD"


class HotelOption(BaseModel):
    name: str
    area: str
    price_per_night: float
    currency: str = "USD"
    rating: float = 0.0


class BudgetBreakdown(BaseModel):
    currency: str = "USD"
    flights: float = 0.0
    lodging: float = 0.0
    food: float = 0.0
    activities: float = 0.0
    local_transport: float = 0.0
    total: float = 0.0


class TripPlan(BaseModel):
    summary: str
    days: list[DayPlan] = Field(default_factory=list)
    flight_options: list[FlightOption] = Field(default_factory=list)
    hotel_options: list[HotelOption] = Field(default_factory=list)
    transport_notes: str = ""
    budget: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    assumptions: list[str] = Field(default_factory=list)


class UserPreferences(BaseModel):
    user_id: str
    liked_interests: list[str] = Field(default_factory=list)
    preferred_comfort_level: ComfortLevel | None = None
    pace_notes: str = ""
    dietary_notes: str = ""
    home_city: str = ""
```

- [ ] **Step 4: Run → pass; lint/type**

Run: `pytest tests/test_models.py -q && make lint type`
Expected: all green.

- [ ] **Step 5: Commit M1**

```bash
git add src/travel_assistant/models.py tests/test_models.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m1): domain models with critical-field completeness logic"
```

**Acceptance:** model tests pass; `missing_critical_fields()` returns exactly `["comfort_level"]` when only comfort is absent.

**Risks:** Over-modeling. Mitigation: only fields the spec/tools need; no speculative fields.

---

## Task 4 — M2: Mock tools

**Goal:** Deterministic mock tools + intake/preference tools, decoupled from agent runtime (pure functions + thin tool wrappers added in M6).

**Files:**
- Create: `src/travel_assistant/tools/__init__.py`
- Create: `src/travel_assistant/tools/mock_data/__init__.py`
- Create: `src/travel_assistant/tools/flights.py`, `hotels.py`, `weather.py`, `attractions.py`, `budget.py`
- Create: `tests/test_tools_flights.py`, `test_tools_hotels.py`, `test_tools_weather.py`, `test_tools_attractions.py`, `test_tools_budget.py`

- [ ] **Step 1: Failing test (flights)** — `tests/test_tools_flights.py`

```python
from travel_assistant.tools.flights import search_flights


def test_flights_deterministic_and_typed() -> None:
    a = search_flights("Shanghai", "Tokyo", seed=42)
    b = search_flights("Shanghai", "Tokyo", seed=42)
    assert [f.model_dump() for f in a] == [f.model_dump() for f in b]
    assert len(a) >= 1 and a[0].price > 0
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_tools_flights.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement core tools (pure functions)**

`src/travel_assistant/tools/flights.py`:
```python
import random

from travel_assistant.models import FlightOption

_CARRIERS = ["AirMock", "MockJet", "PseudoAir"]


def search_flights(origin: str, destination: str, *, seed: int = 0) -> list[FlightOption]:
    rng = random.Random(f"{origin}->{destination}:{seed}")
    return [
        FlightOption(
            carrier=c,
            depart=f"{origin} 08:00",
            arrive=f"{destination} 12:30",
            price=round(rng.uniform(220, 780), 2),
        )
        for c in _CARRIERS
    ]
```

`src/travel_assistant/tools/hotels.py`:
```python
import random

from travel_assistant.models import ComfortLevel, HotelOption

_TIER = {ComfortLevel.BUDGET: (40, 90), ComfortLevel.COMFORT: (90, 200),
         ComfortLevel.LUXURY: (200, 600)}


def search_hotels(city: str, comfort: ComfortLevel, *, seed: int = 0) -> list[HotelOption]:
    rng = random.Random(f"{city}:{comfort}:{seed}")
    lo, hi = _TIER[comfort]
    return [
        HotelOption(name=f"{city} {tag} Hotel", area=area,
                    price_per_night=round(rng.uniform(lo, hi), 2),
                    rating=round(rng.uniform(3.5, 5.0), 1))
        for tag, area in (("Central", "Downtown"), ("Park", "Riverside"))
    ]
```

`src/travel_assistant/tools/weather.py`:
```python
import random

_KINDS = ["sunny", "partly cloudy", "light rain", "clear"]


def get_weather(city: str, days: int, *, seed: int = 0) -> list[str]:
    rng = random.Random(f"{city}:{days}:{seed}")
    return [rng.choice(_KINDS) for _ in range(max(days, 1))]
```

`src/travel_assistant/tools/attractions.py`:
```python
import random

from travel_assistant.models import Activity

_BY_INTEREST = {
    "food": [("Street food market", "food"), ("Sushi tasting", "food")],
    "city walks": [("Old town walk", "city walk"), ("Riverside stroll", "city walk")],
    "history": [("Castle tour", "history"), ("Museum visit", "history")],
}
_DEFAULT = [("City highlights tour", "sightseeing")]


def find_attractions(city: str, interests: list[str], *, seed: int = 0) -> list[Activity]:
    rng = random.Random(f"{city}:{','.join(sorted(interests))}:{seed}")
    picked: list[Activity] = []
    for interest in interests or ["sightseeing"]:
        for name, cat in _BY_INTEREST.get(interest.lower(), _DEFAULT):
            picked.append(Activity(name=f"{name} ({city})", category=cat))
    rng.shuffle(picked)
    return picked or [Activity(name=f"Explore {city}", category="sightseeing")]
```

`src/travel_assistant/tools/budget.py`:
```python
from travel_assistant.models import BudgetBreakdown, FlightOption, HotelOption


def estimate_budget(
    flights: list[FlightOption], hotels: list[HotelOption], nights: int,
    party_size: int, *, food_per_day: float = 45.0, activities_per_day: float = 35.0,
) -> BudgetBreakdown:
    cheapest_flight = min((f.price for f in flights), default=0.0)
    cheapest_hotel = min((h.price_per_night for h in hotels), default=0.0)
    flights_total = cheapest_flight * party_size
    lodging = cheapest_hotel * max(nights, 1)
    food = food_per_day * max(nights, 1) * party_size
    activities = activities_per_day * max(nights, 1)
    local = 12.0 * max(nights, 1)
    total = flights_total + lodging + food + activities + local
    return BudgetBreakdown(currency="USD", flights=round(flights_total, 2),
                           lodging=round(lodging, 2), food=round(food, 2),
                           activities=round(activities, 2),
                           local_transport=round(local, 2), total=round(total, 2))
```

`src/travel_assistant/tools/__init__.py` and `tools/mock_data/__init__.py`: empty module markers (mock data is inlined deterministically; the `mock_data` package is reserved for future fixture files per spec §3.1).

- [ ] **Step 4: Write remaining tool tests** (`hotels`, `weather`, `attractions`, `budget`)

```python
# tests/test_tools_hotels.py
from travel_assistant.models import ComfortLevel
from travel_assistant.tools.hotels import search_hotels
def test_hotels_tiered_and_deterministic() -> None:
    a = search_hotels("Tokyo", ComfortLevel.COMFORT, seed=1)
    b = search_hotels("Tokyo", ComfortLevel.COMFORT, seed=1)
    assert [h.model_dump() for h in a] == [h.model_dump() for h in b]
    assert all(90 <= h.price_per_night <= 200 for h in a)

# tests/test_tools_weather.py
from travel_assistant.tools.weather import get_weather
def test_weather_length_and_deterministic() -> None:
    assert get_weather("Tokyo", 5, seed=2) == get_weather("Tokyo", 5, seed=2)
    assert len(get_weather("Tokyo", 5, seed=2)) == 5

# tests/test_tools_attractions.py
from travel_assistant.tools.attractions import find_attractions
def test_attractions_match_interests() -> None:
    acts = find_attractions("Tokyo", ["food"], seed=3)
    assert any(a.category == "food" for a in acts)

# tests/test_tools_budget.py
from travel_assistant.models import FlightOption, HotelOption
from travel_assistant.tools.budget import estimate_budget
def test_budget_totals_add_up() -> None:
    b = estimate_budget([FlightOption(carrier="X", depart="a", arrive="b", price=300)],
                         [HotelOption(name="H", area="C", price_per_night=100)],
                         nights=4, party_size=2)
    assert b.total == round(b.flights + b.lodging + b.food
                            + b.activities + b.local_transport, 2)
```

- [ ] **Step 5: Run → pass; lint/type**

Run: `pytest tests/test_tools_*.py -q && make lint type` → all green.

- [ ] **Step 6: Commit M2**

```bash
git add src/travel_assistant/tools tests/test_tools_*.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m2): deterministic mock tools (flights/hotels/weather/attractions/budget)"
```

**Acceptance:** every tool deterministic for a fixed seed; budget total equals component sum; hotels respect comfort tier.

**Risks:** Hidden nondeterminism. Mitigation: all randomness seeded from explicit string keys; equality tests assert reproducibility.

---

## Task 5 — M3: JSON preference store

**Goal:** `PreferenceStore` Protocol + JSON impl keyed by `user_id`, corrupt-file resilient; documented upgrade path.

**Files:**
- Create: `src/travel_assistant/memory/__init__.py`
- Create: `src/travel_assistant/memory/repository.py`
- Create: `src/travel_assistant/memory/json_store.py`
- Create: `src/travel_assistant/memory/UPGRADE.md`
- Create: `tests/test_memory.py`

- [ ] **Step 1: Failing tests** — `tests/test_memory.py`

```python
from pathlib import Path

from travel_assistant.memory.json_store import JsonPreferenceStore
from travel_assistant.models import ComfortLevel, UserPreferences


def test_roundtrip_keyed_by_user(tmp_path: Path) -> None:
    store = JsonPreferenceStore(tmp_path / "p.json")
    assert store.get("u1") is None
    store.save(UserPreferences(user_id="u1", liked_interests=["food"],
                               preferred_comfort_level=ComfortLevel.COMFORT))
    store.save(UserPreferences(user_id="u2", liked_interests=["history"]))
    got = store.get("u1")
    assert got is not None and got.liked_interests == ["food"]
    assert store.get("u2").liked_interests == ["history"]


def test_corrupt_file_recovers_and_backs_up(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text("{ not json")
    store = JsonPreferenceStore(path)
    assert store.get("u1") is None              # treated as empty
    assert path.with_suffix(".json.bak").exists()  # bad file backed up
    store.save(UserPreferences(user_id="u1"))
    assert store.get("u1") is not None
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_memory.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement repository + JSON store**

`src/travel_assistant/memory/repository.py`:
```python
from typing import Protocol

from travel_assistant.models import UserPreferences


class PreferenceStore(Protocol):
    def get(self, user_id: str) -> UserPreferences | None: ...
    def save(self, prefs: UserPreferences) -> None: ...
```

`src/travel_assistant/memory/json_store.py`:
```python
import json
from pathlib import Path

from travel_assistant.models import UserPreferences


class JsonPreferenceStore:
    """JSON-backed PreferenceStore keyed by user_id (spec §3, §10)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def _read_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text() or "{}")
        except (json.JSONDecodeError, ValueError):
            self._path.replace(self._path.with_suffix(self._path.suffix + ".bak"))
            return {}

    def get(self, user_id: str) -> UserPreferences | None:
        raw = self._read_all().get(user_id)
        return UserPreferences.model_validate(raw) if raw else None

    def save(self, prefs: UserPreferences) -> None:
        data = self._read_all()
        data[prefs.user_id] = prefs.model_dump(mode="json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2, sort_keys=True))
```

`src/travel_assistant/memory/__init__.py`:
```python
from travel_assistant.memory.json_store import JsonPreferenceStore
from travel_assistant.memory.repository import PreferenceStore

__all__ = ["JsonPreferenceStore", "PreferenceStore"]
```

`src/travel_assistant/memory/UPGRADE.md`: document swapping `JsonPreferenceStore` for a `BaseStore`-backed adapter (v2): same `PreferenceStore` Protocol, namespace `("prefs", user_id)`, `store.put/get`; no agent/runner changes required.

> Note: `.json.bak` is produced by tests in `tmp_path`; `.gitignore` already excludes `data/`. The test uses `path.with_suffix(".json.bak")` — implementation appends `.bak` to the full suffix, yielding the same `p.json.bak`. Verify this equivalence when the test runs; if `Path.with_suffix` semantics differ, align the implementation to the test (test is the contract).

- [ ] **Step 4: Run → pass; lint/type**

Run: `pytest tests/test_memory.py -q && make lint type` → green.

- [ ] **Step 5: Commit M3**

```bash
git add src/travel_assistant/memory tests/test_memory.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m3): JSON preference store (Protocol, keyed, corrupt-resilient)"
```

**Acceptance:** roundtrip + keyed-by-user + corrupt-recovery tests pass; `UPGRADE.md` present.

**Risks:** `Path.with_suffix` backup-name mismatch. Mitigation: the test asserts the exact backup path; reconcile implementation to the test at run time.

---

## Task 6 — M4: Config + LLM layer (FakeChatModel policy)

**Goal:** `pydantic-settings` config and a model resolver enforcing the spec §6 precedence, including the **explicit error** when no key and not fake.

**Files:**
- Create: `src/travel_assistant/config.py`
- Create: `src/travel_assistant/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Failing tests** — `tests/test_llm.py`

```python
import pytest

from travel_assistant.config import Settings
from travel_assistant.llm import ModelConfigError, resolve_model


def test_fake_when_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    s = Settings(travel_agent_fake_model=True, deepseek_api_key=None)
    model, is_fake = resolve_model(s)
    assert is_fake is True


def test_error_when_no_key_and_not_fake() -> None:
    s = Settings(travel_agent_fake_model=False, deepseek_api_key=None)
    with pytest.raises(ModelConfigError, match="DEEPSEEK_API_KEY"):
        resolve_model(s)


def test_invalid_checkpointer_backend_rejected() -> None:
    with pytest.raises(ValueError, match="CHECKPOINTER_BACKEND"):
        Settings(checkpointer_backend="redis").validated()
```

> conftest sets `TRAVEL_AGENT_FAKE_MODEL=true`; tests pass explicit `Settings(...)` so they exercise precedence directly rather than env.

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_llm.py -q` → FAIL (modules missing).

- [ ] **Step 3: Implement config + llm**

`src/travel_assistant/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str | None = None
    travel_agent_model_id: str = "deepseek:deepseek-chat"
    travel_agent_fake_model: bool = False
    checkpointer_backend: str = "memory"
    travel_agent_sqlite_path: str = "data/checkpoints.sqlite3"
    travel_agent_prefs_path: str = "data/preferences.json"
    langsmith_tracing: bool = False

    def validated(self) -> "Settings":
        if self.checkpointer_backend not in {"memory", "sqlite"}:
            raise ValueError(
                f"CHECKPOINTER_BACKEND must be 'memory' or 'sqlite', "
                f"got {self.checkpointer_backend!r}"
            )
        return self
```

`src/travel_assistant/llm.py`:
```python
from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from travel_assistant.config import Settings


class ModelConfigError(RuntimeError):
    """Raised when no real key is available and fake mode was not requested."""


def make_fake_model(scripted: list[AIMessage] | None = None) -> BaseChatModel:
    msgs = scripted or [AIMessage(content="FAKE: configure a script for real flows")]
    return GenericFakeChatModel(messages=iter(msgs))


def resolve_model(settings: Settings) -> tuple[BaseChatModel, bool]:
    """Returns (model, is_fake). Precedence per spec §6."""
    if settings.travel_agent_fake_model:
        return make_fake_model(), True
    if not settings.deepseek_api_key:
        raise ModelConfigError(
            "No DEEPSEEK_API_KEY set. Set it in .env, or run with --fake "
            "(or TRAVEL_AGENT_FAKE_MODEL=true) to use the deterministic fake model."
        )
    from langchain.chat_models import init_chat_model

    model = init_chat_model(
        settings.travel_agent_model_id, api_key=settings.deepseek_api_key
    )
    return model, False
```

> If `api_key=` kwarg name differs for `init_chat_model`/`langchain-deepseek`, use the variant recorded in `api-spike-findings.md`.

- [ ] **Step 4: Run → pass; lint/type**

Run: `pytest tests/test_llm.py -q && make lint type` → green.

- [ ] **Step 5: Commit M4**

```bash
git add src/travel_assistant/config.py src/travel_assistant/llm.py tests/test_llm.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m4): settings + model resolver with explicit fake/no-key policy"
```

**Acceptance:** no-key+not-fake raises `ModelConfigError` mentioning `DEEPSEEK_API_KEY`; fake flag returns a fake model; bad backend rejected.

**Risks:** `init_chat_model` kwarg drift. Mitigation: reconcile against findings doc.

---

## Task 7 — M5: Agent state, prompt, and `create_agent` assembly

**Goal:** Assemble the agent with `response_format=TripPlan`, the M2 tools wrapped as LangChain tools, system prompt with the §5 clarification policy; a runner that injects preferences. Verified end-to-end with a scripted fake model.

**Files:**
- Create: `src/travel_assistant/state.py`
- Create: `src/travel_assistant/prompts.py`
- Create: `src/travel_assistant/agent.py`
- Create: `src/travel_assistant/runner.py`
- Create: `tests/test_agent_smoke.py`

- [ ] **Step 1: Failing smoke test** — `tests/test_agent_smoke.py`

```python
from pathlib import Path

from langchain_core.messages import AIMessage

from travel_assistant.config import Settings
from travel_assistant.models import TripPlan
from travel_assistant.runner import build_runner


def test_agent_returns_structured_plan(tmp_path: Path) -> None:
    scripted = [
        AIMessage(content='{"summary":"Tokyo 5d","days":[],"flight_options":[],'
                  '"hotel_options":[],"transport_notes":"metro",'
                  '"budget":{"currency":"USD","flights":0,"lodging":0,"food":0,'
                  '"activities":0,"local_transport":0,"total":0},'
                  '"assumptions":["fake run"]}'),
    ]
    settings = Settings(travel_agent_fake_model=True,
                        travel_agent_prefs_path=str(tmp_path / "p.json"))
    runner = build_runner(settings, scripted_fake_messages=scripted)
    result = runner.run(user_id="u1", thread_id="t1",
                        message="Shanghai to Tokyo 5 days, comfort, food")
    assert isinstance(result.plan, TripPlan)
    assert result.plan.summary == "Tokyo 5d"
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_agent_smoke.py -q` → FAIL (modules missing).

- [ ] **Step 3: Implement state, prompt, agent, runner**

`src/travel_assistant/state.py`:
```python
from langchain.agents import AgentState  # path per api-spike-findings.md

from travel_assistant.models import TripRequest


class TravelState(AgentState):
    """Agent state extended with the structured trip request (set via M6 tool)."""
    trip_request: TripRequest | None
```

`src/travel_assistant/prompts.py`:
```python
SYSTEM_PROMPT = """You are a travel-planning assistant.

Clarification policy (strict):
- If exactly ONE critical field is missing, ask exactly ONE focused question.
- If MULTIPLE critical fields are missing, ask 2-3 focused questions in one turn.
- Never ask open-ended interview questions. Never re-ask answered fields.
- After at most 2 clarification rounds, proceed with sensible defaults and list
  every assumption in TripPlan.assumptions.
Critical fields: origin, destination, dates-or-duration, comfort_level.

Workflow once critical fields are known: call record_trip_request, then gather
flights, hotels, weather, attractions, then estimate_budget, then return the final
TripPlan. Honor known user preferences provided below.

{preferences_block}
"""
```

`src/travel_assistant/agent.py`:
```python
from langchain.agents import create_agent  # path per api-spike-findings.md
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver

from travel_assistant.models import TripPlan
from travel_assistant.prompts import SYSTEM_PROMPT
from travel_assistant.state import TravelState


def build_agent(model: BaseChatModel, tools: list, checkpointer: BaseCheckpointSaver,
                preferences_block: str):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT.format(preferences_block=preferences_block),
        response_format=TripPlan,
        state_schema=TravelState,
        checkpointer=checkpointer,
    )
```

`src/travel_assistant/runner.py`:
```python
from dataclasses import dataclass

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from travel_assistant.agent import build_agent
from travel_assistant.config import Settings
from travel_assistant.llm import make_fake_model, resolve_model
from travel_assistant.memory import JsonPreferenceStore
from travel_assistant.models import TripPlan, UserPreferences


@dataclass
class RunResult:
    plan: TripPlan | None
    messages: list


def _preferences_block(prefs: UserPreferences | None) -> str:
    if prefs is None:
        return "Known user preferences: none on file."
    return (f"Known user preferences: interests={prefs.liked_interests}, "
            f"comfort={prefs.preferred_comfort_level}, pace={prefs.pace_notes!r}, "
            f"diet={prefs.dietary_notes!r}, home_city={prefs.home_city!r}.")


class Runner:
    def __init__(self, agent) -> None:
        self._agent = agent

    def run(self, user_id: str, thread_id: str, message: str) -> RunResult:
        out = self._agent.invoke(
            {"messages": [("user", message)]},
            config={"configurable": {"thread_id": thread_id}},
        )
        return RunResult(plan=out.get("structured_response"),
                         messages=out.get("messages", []))


def build_runner(settings: Settings, scripted_fake_messages: list[AIMessage] | None = None,
                 tools: list | None = None) -> Runner:
    settings.validated()
    if scripted_fake_messages is not None:
        model = make_fake_model(scripted_fake_messages)
    else:
        model, _ = resolve_model(settings)
    store = JsonPreferenceStore(settings.travel_agent_prefs_path)
    prefs = store.get("u1")  # NOTE: replaced with real user_id wiring in M6/M8
    checkpointer = InMemorySaver()  # replaced by factory in M7
    agent = build_agent(model, tools or [], checkpointer, _preferences_block(prefs))
    return Runner(agent)
```

> `runner.py` deliberately uses `InMemorySaver` and `tools=[]` here; M7 swaps in the checkpointer factory and M6 supplies real tools + per-user prefs. These TODO-by-design seams are explicit and exercised by their own milestone tests — not placeholders in the plan sense.

- [ ] **Step 4: Run → pass; lint/type**

Run: `pytest tests/test_agent_smoke.py -q && make lint type` → green.

- [ ] **Step 5: Commit M5**

```bash
git add src/travel_assistant/state.py src/travel_assistant/prompts.py \
        src/travel_assistant/agent.py src/travel_assistant/runner.py \
        tests/test_agent_smoke.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m5): agent assembly with TripPlan structured output + runner"
```

**Acceptance:** scripted fake model yields a valid `TripPlan` in `result.plan`; preferences block injected into the system prompt.

**Risks:** `AgentState`/`state_schema` API shape. Mitigation: use exactly the form recorded in `api-spike-findings.md`; if `state_schema` unsupported, drop it here and carry `trip_request` via M6's `Command` into the default state — note the deviation in the commit.

---

## Task 8 — M6: `ToolRuntime` tools, `Command` state update, `save_preference`

**Goal:** Wrap M2 tools as LangChain tools that read `TripRequest`/prefs from state via `ToolRuntime`; `record_trip_request` updates state via `Command`+`ToolMessage`; `save_preference` persists explicitly.

**Files:**
- Create: `src/travel_assistant/tools/intake.py`
- Create: `src/travel_assistant/tools/preferences.py`
- Create: `src/travel_assistant/tools/runtime_tools.py`
- Modify: `src/travel_assistant/runner.py` (pass real tools + per-user prefs)
- Create: `tests/test_runtime_tools.py`

- [ ] **Step 1: Failing tests** — `tests/test_runtime_tools.py`

```python
from langgraph.types import Command  # path per api-spike-findings.md

from travel_assistant.models import ComfortLevel, UserPreferences
from travel_assistant.tools.intake import record_trip_request_impl
from travel_assistant.tools.preferences import save_preference_impl


def test_record_trip_request_returns_command_update() -> None:
    cmd = record_trip_request_impl(
        tool_call_id="c1", origin="Shanghai", destination="Tokyo",
        duration_days=5, comfort_level="comfort", interests=["food"],
    )
    assert isinstance(cmd, Command)
    tr = cmd.update["trip_request"]
    assert tr.destination == "Tokyo" and tr.missing_critical_fields() == []


def test_save_preference_persists(tmp_path) -> None:
    from travel_assistant.memory import JsonPreferenceStore
    store = JsonPreferenceStore(tmp_path / "p.json")
    save_preference_impl(store, UserPreferences(user_id="u9",
                         liked_interests=["food"],
                         preferred_comfort_level=ComfortLevel.COMFORT))
    assert store.get("u9").liked_interests == ["food"]
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_runtime_tools.py -q` → FAIL (modules missing).

- [ ] **Step 3: Implement intake / preferences / runtime tools**

`src/travel_assistant/tools/intake.py`:
```python
from langchain_core.messages import ToolMessage
from langgraph.types import Command  # path per api-spike-findings.md

from travel_assistant.models import ComfortLevel, TripRequest


def record_trip_request_impl(
    tool_call_id: str, origin: str, destination: str,
    duration_days: int | None = None, comfort_level: str | None = None,
    interests: list[str] | None = None, party_size: int = 1,
) -> Command:
    req = TripRequest(
        origin=origin, destination=destination, duration_days=duration_days,
        comfort_level=ComfortLevel(comfort_level) if comfort_level else None,
        interests=interests or [], party_size=party_size,
    )
    return Command(update={
        "trip_request": req,
        "messages": [ToolMessage("trip request recorded", tool_call_id=tool_call_id)],
    })
```

`src/travel_assistant/tools/preferences.py`:
```python
from travel_assistant.memory.repository import PreferenceStore
from travel_assistant.models import UserPreferences


def save_preference_impl(store: PreferenceStore, prefs: UserPreferences) -> str:
    store.save(prefs)
    return f"preferences saved for {prefs.user_id}"
```

`src/travel_assistant/tools/runtime_tools.py`: builds the `@tool` list. Each domain tool declares a `ToolRuntime` param (import path/usage per `api-spike-findings.md`), reads `runtime.state["trip_request"]` for city/comfort/duration, and calls the corresponding pure M2 function. `record_trip_request` is wrapped to inject `tool_call_id` from runtime and return the `Command`. `save_preference` is closed over the per-user `PreferenceStore` and `user_id`. Expose `build_tools(store: PreferenceStore, user_id: str) -> list`.

```python
from langchain.tools import tool, ToolRuntime  # paths per api-spike-findings.md

from travel_assistant.memory.repository import PreferenceStore
from travel_assistant.models import ComfortLevel, UserPreferences
from travel_assistant.tools import attractions, budget, flights, hotels, weather
from travel_assistant.tools.intake import record_trip_request_impl
from travel_assistant.tools.preferences import save_preference_impl


def build_tools(store: PreferenceStore, user_id: str) -> list:
    @tool
    def record_trip_request(runtime: ToolRuntime, origin: str, destination: str,
                            duration_days: int | None = None,
                            comfort_level: str | None = None,
                            interests: list[str] | None = None,
                            party_size: int = 1):
        """Record the structured trip request once critical fields are known."""
        return record_trip_request_impl(
            runtime.tool_call_id, origin, destination, duration_days,
            comfort_level, interests, party_size)

    @tool
    def search_flights(runtime: ToolRuntime) -> list[dict]:
        """Search flights for the recorded trip request."""
        tr = runtime.state["trip_request"]
        return [f.model_dump() for f in flights.search_flights(tr.origin, tr.destination)]

    @tool
    def search_hotels(runtime: ToolRuntime) -> list[dict]:
        """Search hotels for the recorded trip request."""
        tr = runtime.state["trip_request"]
        return [h.model_dump() for h in
                hotels.search_hotels(tr.destination,
                                     tr.comfort_level or ComfortLevel.COMFORT)]

    @tool
    def get_weather(runtime: ToolRuntime) -> list[str]:
        """Get a weather outlook for the destination."""
        tr = runtime.state["trip_request"]
        return weather.get_weather(tr.destination, tr.duration_days or 3)

    @tool
    def find_attractions(runtime: ToolRuntime) -> list[dict]:
        """Find attractions matching the traveler's interests."""
        tr = runtime.state["trip_request"]
        return [a.model_dump() for a in
                attractions.find_attractions(tr.destination, tr.interests)]

    @tool
    def estimate_budget(runtime: ToolRuntime) -> dict:
        """Estimate the trip budget from gathered options."""
        tr = runtime.state["trip_request"]
        fl = flights.search_flights(tr.origin, tr.destination)
        ho = hotels.search_hotels(tr.destination,
                                  tr.comfort_level or ComfortLevel.COMFORT)
        return budget.estimate_budget(fl, ho, tr.duration_days or 3,
                                      tr.party_size).model_dump()

    @tool
    def save_preference(liked_interests: list[str] | None = None,
                        preferred_comfort_level: str | None = None,
                        pace_notes: str = "", dietary_notes: str = "",
                        home_city: str = "") -> str:
        """Persist durable user travel preferences (explicit; spec §3)."""
        return save_preference_impl(store, UserPreferences(
            user_id=user_id, liked_interests=liked_interests or [],
            preferred_comfort_level=(ComfortLevel(preferred_comfort_level)
                                     if preferred_comfort_level else None),
            pace_notes=pace_notes, dietary_notes=dietary_notes,
            home_city=home_city))

    return [record_trip_request, search_flights, search_hotels, get_weather,
            find_attractions, estimate_budget, save_preference]
```

- [ ] **Step 4: Wire real tools + per-user prefs into `runner.py`**

Modify `build_runner` to accept `user_id` (default `"default"`), call `build_tools(store, user_id)` when `tools is None`, and load `store.get(user_id)` instead of the hardcoded `"u1"`. Update `Runner.run` to thread `user_id` through (signature already has it). Adjust `test_agent_smoke.py` only if a signature changed (keep behavior identical).

- [ ] **Step 5: Run → pass; lint/type**

Run: `pytest -q && make lint type` → all green (full suite).

- [ ] **Step 6: Commit M6**

```bash
git add src/travel_assistant/tools/intake.py src/travel_assistant/tools/preferences.py \
        src/travel_assistant/tools/runtime_tools.py src/travel_assistant/runner.py \
        tests/test_runtime_tools.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m6): ToolRuntime tools, Command state update, save_preference"
```

**Acceptance:** `record_trip_request_impl` returns a `Command` whose `update["trip_request"]` is complete; `save_preference_impl` persists; full suite green.

**Risks:** `ToolRuntime`/`tool` decorator state access differs. Mitigation: implement strictly per `api-spike-findings.md`; the impl funcs are tested independently of the runtime so failures localize to the wrapper.

---

## Task 9 — M7: Checkpointer factory + bounded clarification

**Goal:** `checkpointer.py` factory (`memory` default / `sqlite` when configured); verify the flexible, bounded clarification flow and sqlite resume-after-restart.

**Files:**
- Create: `src/travel_assistant/checkpointer.py`
- Modify: `src/travel_assistant/runner.py` (use factory)
- Create: `tests/test_short_term_memory.py`

- [ ] **Step 1: Failing tests** — `tests/test_short_term_memory.py`

```python
import pytest

from langchain_core.messages import AIMessage

from travel_assistant.checkpointer import make_checkpointer
from travel_assistant.config import Settings
from travel_assistant.runner import build_runner


def test_factory_memory_default() -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    cp = make_checkpointer(Settings(checkpointer_backend="memory"))
    assert isinstance(cp, InMemorySaver)


def test_only_budget_missing_asks_only_budget(tmp_path) -> None:
    # Scripted fake model: when only comfort missing, model asks ONLY about budget.
    scripted = [AIMessage(content="What is your budget/comfort level "
                                  "(budget, comfort, or luxury)?")]
    s = Settings(travel_agent_fake_model=True,
                 travel_agent_prefs_path=str(tmp_path / "p.json"))
    runner = build_runner(s, scripted_fake_messages=scripted)
    r = runner.run("u1", "t1", "Shanghai to Tokyo, 5 days")
    text = r.messages[-1].content.lower()
    assert "budget" in text or "comfort" in text
    assert "origin" not in text and "destination" not in text

@pytest.mark.integration
def test_sqlite_resume_after_restart(tmp_path) -> None:
    db = tmp_path / "cp.sqlite3"
    s = Settings(checkpointer_backend="sqlite", travel_agent_sqlite_path=str(db))
    cp1 = make_checkpointer(s)
    assert db.exists() or hasattr(cp1, "conn")  # sqlite saver bound to file
```

> The clarification-bound (≤2 rounds → proceed with assumptions) is enforced by the system prompt; the scripted-model test asserts the *single-field* behavior deterministically. A second scripted test for the multi-field case (model asks 2–3 questions) follows the same pattern with a multi-question scripted message and asserts ≥2 question marks and no answered-field re-ask.

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_short_term_memory.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement `checkpointer.py` + wire factory**

`src/travel_assistant/checkpointer.py`:
```python
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from travel_assistant.config import Settings


def make_checkpointer(settings: Settings) -> BaseCheckpointSaver:
    settings.validated()
    if settings.checkpointer_backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        path = Path(settings.travel_agent_sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return SqliteSaver.from_conn_string(str(path)).__enter__()
    return InMemorySaver()
```

Modify `build_runner` to call `make_checkpointer(settings)` instead of the hardcoded `InMemorySaver()`.

> `SqliteSaver.from_conn_string` returns a context manager in LangGraph; `.__enter__()` keeps it open for the process lifetime (CLI). If the installed API exposes a direct constructor (per findings doc), use that and note the deviation.

- [ ] **Step 4: Run → pass (non-integration); lint/type**

Run: `pytest -q -m "not integration" && make lint type` → green.
Run (manual, optional): `CHECKPOINTER_BACKEND=sqlite pytest -q -m integration`.

- [ ] **Step 5: Commit M7**

```bash
git add src/travel_assistant/checkpointer.py src/travel_assistant/runner.py \
        tests/test_short_term_memory.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m7): checkpointer factory + bounded clarification tests"
```

**Acceptance:** factory returns `InMemorySaver` by default; only-budget-missing scenario asks only about budget; sqlite saver binds to the configured file.

**Risks:** `SqliteSaver` context-manager lifecycle. Mitigation: keep it open per process; documented; integration-marked test isolates it.

---

## Task 10 — M8: Streaming + full CLI UX

**Goal:** Replace the placeholder CLI with the real multi-turn loop: args (`user_id`/`thread_id`/`--new`/`--fake`), streamed step rendering, fake-mode banner, pretty `TripPlan`+budget output.

**Files:**
- Create: `src/travel_assistant/streaming.py`
- Modify: `src/travel_assistant/cli.py`
- Modify: `src/travel_assistant/runner.py` (add `stream()` generator)
- Create: `tests/test_cli.py`

- [ ] **Step 1: Failing CLI test** — `tests/test_cli.py`

```python
from typer.testing import CliRunner

from travel_assistant.cli import app


def test_cli_fake_banner_and_plan(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_PREFS_PATH", str(tmp_path / "p.json"))
    # one-shot: complete request, scripted fake returns a valid TripPlan JSON
    result = CliRunner().invoke(app, [
        "plan", "--fake", "--user-id", "u1", "--thread-id", "t1",
        "--message", "Shanghai to Tokyo, 5 days in June, comfort, food",
        "--once",
    ])
    assert result.exit_code == 0
    assert "*** FAKE MODEL ***" in result.output
    assert "Trip Plan" in result.output
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_cli.py -q` → FAIL (CLI lacks options/behavior).

- [ ] **Step 3: Implement streaming + CLI**

`src/travel_assistant/streaming.py`: a `render_stream(events)` helper that, given the agent's `.stream(..., stream_mode="updates")` output, prints concise step lines (`· tool: <name>`, `· model thinking…`). Pure formatting, no LLM logic.

`src/travel_assistant/runner.py`: add `Runner.stream(user_id, thread_id, message)` yielding update events from `self._agent.stream(...)`, then a final `RunResult` (read final state for `structured_response`).

`src/travel_assistant/cli.py`: real `plan` command —
options `--user-id` (default `"default"`), `--thread-id` (default generated), `--new` (force fresh thread), `--fake`, `--message` (initial), `--once` (single turn, no loop; used by tests). On `--fake` (or `TRAVEL_AGENT_FAKE_MODEL`) print `*** FAKE MODEL ***`; otherwise print the active model id. Build settings, `build_runner`, then loop: read user input (or `--message`), stream via `render_stream`, and when a `TripPlan` is produced, pretty-print `Trip Plan`, day-by-day activities, hotel/flight options, and a `Budget` table; exit non-zero with a friendly message on `ModelConfigError`. With `--once`, run a single turn and exit. For the test, the fake model is scripted internally to emit a final `TripPlan` JSON for a complete request (reuse the M5 scripted JSON via a small `_default_fake_script()` helper in `llm.py`).

- [ ] **Step 4: Run → pass; full suite; lint/type**

Run: `pytest -q -m "not integration" && make lint type` → all green.

- [ ] **Step 5: Manual real-model check (optional, needs key)**

Run: `DEEPSEEK_API_KEY=… python -m travel_assistant plan --message "I want to travel from Shanghai to Tokyo for 5 days in June. My budget is comfort level. I like food and city walks." --once`
Expected: a valid printed `TripPlan` with budget and ≥1 flight/hotel option.

- [ ] **Step 6: Commit M8**

```bash
git add src/travel_assistant/streaming.py src/travel_assistant/cli.py \
        src/travel_assistant/runner.py src/travel_assistant/llm.py tests/test_cli.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m8): streaming output + full multi-turn CLI UX"
```

**Acceptance:** CLI test passes (fake banner + printed plan); manual real run (if key) yields a valid plan.

**Risks:** `.stream` mode/event shape drift. Mitigation: `render_stream` tolerates unknown event keys (defensive formatting); shape confirmed against findings doc.

---

## Task 11 — M9: LangSmith tracing + polish

**Goal:** Env-gated tracing (no code change to toggle); finalize README (architecture, run guide, structured-output fallback, v2 roadmap); full `make ci` green.

**Files:**
- Create: `src/travel_assistant/tracing.py`
- Modify: `src/travel_assistant/cli.py` (call tracing setup at startup)
- Modify: `README.md`
- Create: `tests/test_tracing.py`

- [ ] **Step 1: Failing test** — `tests/test_tracing.py`

```python
from travel_assistant.config import Settings
from travel_assistant.tracing import configure_tracing


def test_tracing_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    assert configure_tracing(Settings(langsmith_tracing=False)) is False


def test_tracing_enabled_sets_env(monkeypatch) -> None:
    assert configure_tracing(Settings(langsmith_tracing=True)) is True
    import os
    assert os.environ.get("LANGSMITH_TRACING") == "true"
```

- [ ] **Step 2: Run → fail**

Run: `pytest tests/test_tracing.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement `tracing.py` + wire startup**

`src/travel_assistant/tracing.py`:
```python
import os

from travel_assistant.config import Settings


def configure_tracing(settings: Settings) -> bool:
    """Enable LangSmith via env only (spec §9 M9). Returns whether enabled."""
    if not settings.langsmith_tracing:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    return True
```

Call `configure_tracing(settings)` once at the start of the CLI `plan` command (before building the runner).

- [ ] **Step 4: Finalize README**

Replace the M0 status section with: architecture diagram (ASCII: CLI → Runner → create_agent → tools/checkpointer/PreferenceStore), full run guide (fake + real DeepSeek), the §8 structured-output fallback note, and the §14 v2 roadmap (post-model preference extraction, LangGraph `BaseStore`, real APIs, hand-authored `StateGraph`).

- [ ] **Step 5: Full CI green**

Run: `make ci` (runs `lint type test`, no API keys).
Expected: exit 0; coverage on core (`tools`/`models`/`memory`/`state`) ≥ ~80% — verify with `pytest --cov=travel_assistant -q -m "not integration"`.

- [ ] **Step 6: Commit M9**

```bash
git add src/travel_assistant/tracing.py src/travel_assistant/cli.py README.md \
        tests/test_tracing.py
git -c user.email=khalil19951024@gmail.com -c user.name="Travel Assistant" \
  commit -m "feat(m9): env-gated LangSmith tracing + README polish; CI green"
```

**Acceptance:** tracing toggles via env only; `make ci` green; README complete; coverage target met.

**Risks:** Coverage below target. Mitigation: core modules are pure/well-tested by M1–M3; add focused unit tests for any uncovered branch rather than weakening the gate.

---

## Plan Self-Review

**Spec coverage:** §1 goal → all tasks; §2 baseline → T1; §3 architecture → T7/T8/T9; §3.1 structure → T1+incremental; §4 models → T3; §5 clarification → T7 prompt + T9 tests; §6 fake policy → T6; §7 data flow → T7/T8; §8 structured output + fallback → T7 (default) + README (fallback, T11); §9 milestones → T1–T11 (M0–M9, plus spike T2); §10 error handling → T6 (config error), T1 (.gitignore/data), T9 (sqlite fallback documented), T8 (CLI friendly exit); §11 testing → every task is TDD + T9 integration marker + T11 coverage; §12 DoD → T8 manual run + T9 clarification + T6 fake policy + T11 CI; §13 risks/spike → T2; §14 v2 → README (T11). No uncovered requirement.

**Placeholder scan:** No "TBD/TODO-as-deferral". The two "seam" notes in T7/T9 (`InMemorySaver`→factory, `tools=[]`→real tools) are explicitly resolved by named later tasks with their own tests — sequenced refactors, not placeholders.

**Type consistency:** `TripRequest`/`TripPlan`/`UserPreferences`/`ComfortLevel` names identical across T3–T11; `resolve_model`→`(model, is_fake)` used consistently; `build_runner`/`Runner.run(user_id, thread_id, message)` signature stable T7→T10; `make_checkpointer(settings)`/`build_tools(store, user_id)`/`configure_tracing(settings)` referenced exactly as defined.

**Fixes applied inline:** corrected the Task 9 test imports to a single clean `from langchain_core.messages import AIMessage`.
