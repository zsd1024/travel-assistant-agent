# V1 — Amap Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the Amap (高德地图) Web Service APIs as opt-in real-data providers for POI, weather, route, and geocoding, behind the existing V0 tool surface — with mock providers as the default, no real API calls in CI, and `route_between` added as a new agent tool.

**Architecture:** Approach A — Provider `Protocol` + factory subpackage. Tools call providers via factories selected by `Settings`; mock providers wrap unchanged V0 functions; Amap providers share one `AmapHttpClient` (sync httpx + retry + LRU + key redaction) and fall back per-call to mock on non-CN cities / upstream errors. Tests use `respx`-mocked synthetic Amap JSON; a conftest guard blocks any live HTTP.

**Tech Stack:** Python 3.11, LangChain 1.x `create_agent` (unchanged), Pydantic v2, pydantic-settings, **httpx (promoted to direct dep)**, **respx (new dev dep)**, tenacity (existing), pytest.

**Spec:** `docs/superpowers/specs/2026-05-20-v1-amap-integration-design.md`

**Conventions for every task:** TDD (failing test → minimal code → green → commit). Exact paths. One milestone = one Task = one milestone commit at the end. Pinned versions. `TRAVEL_AGENT_FAKE_MODEL=true` continues to force the deterministic fake model in tests; `AMAP_API_KEY` is force-deleted from the env in tests; the new conftest live-HTTP guard blocks any outbound httpx call not intercepted by respx.

**Commit author:** Use the repo-local git identity (already set to `khalil <65383320+zsd1024@users.noreply.github.com>`); plain `git commit -m "..."` — no `-c user.email/name` flags needed.

**Baseline at start:** branch `main` @ `955327d` (V1 spec committed); **77 tests green**; `make ci` green.

---

## Task 1 — M10: Foundations (deps + Settings + models + Protocols + live-HTTP guard)

**Goal:** Wire the V1 substrate WITHOUT any provider implementation. After this task: `httpx` is a direct dep, `respx` is a dev dep, `Settings` has the new fields with fail-fast validation, `Activity` is unchanged, `GeocodeResult`/`RouteResult` exist, the `providers/` subpackage has the four `Protocol`s only, `tests/conftest.py` blocks live HTTP, and **77 prior tests stay green** alongside the new foundation tests.

> ⚠️ Scope guard: do NOT implement any mock or Amap provider in this task. Do NOT add factories yet. Do NOT touch `runtime_tools.py`/`runner.py`. Those live in M11 and M16.

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/travel_assistant/config.py`
- Modify: `src/travel_assistant/models.py`
- Modify: `.env.example`
- Modify: `tests/conftest.py`
- Create: `src/travel_assistant/providers/__init__.py`
- Create: `src/travel_assistant/providers/poi.py`
- Create: `src/travel_assistant/providers/weather.py`
- Create: `src/travel_assistant/providers/route.py`
- Create: `src/travel_assistant/providers/geocoding.py`
- Create: `tests/test_settings_amap.py`

- [ ] **Step 1: Write failing Settings/validated tests** — `tests/test_settings_amap.py`

```python
import importlib

import pytest

from travel_assistant.config import Settings


def test_default_providers_are_mock_and_no_key_required() -> None:
    s = Settings().validated()
    assert s.travel_agent_provider_poi == "mock"
    assert s.travel_agent_provider_weather == "mock"
    assert s.travel_agent_provider_route == "mock"
    assert s.travel_agent_provider_geocoding == "mock"
    assert s.amap_api_key is None  # no key required for default mock path


def test_unknown_provider_value_rejected() -> None:
    with pytest.raises(ValueError, match="TRAVEL_AGENT_PROVIDER_POI"):
        Settings(travel_agent_provider_poi="redis").validated()


def test_amap_without_key_fails_fast() -> None:
    with pytest.raises(ValueError, match="AMAP_API_KEY"):
        Settings(
            travel_agent_provider_poi="amap", amap_api_key=None
        ).validated()


def test_amap_with_key_validates() -> None:
    s = Settings(
        travel_agent_provider_poi="amap",
        travel_agent_provider_weather="amap",
        amap_api_key="amap-test-key",
    ).validated()
    assert s.amap_api_key == "amap-test-key"


def test_protocols_import() -> None:
    # Protocols-only foundation: the 4 modules must import cleanly.
    for mod in (
        "travel_assistant.providers.poi",
        "travel_assistant.providers.weather",
        "travel_assistant.providers.route",
        "travel_assistant.providers.geocoding",
    ):
        importlib.import_module(mod)
```

- [ ] **Step 2: Write failing live-HTTP-guard test** — append to `tests/test_settings_amap.py`

```python
def test_live_http_is_blocked_outside_respx() -> None:
    # The autouse conftest fixture must make an unintercepted httpx call raise.
    import httpx

    with pytest.raises(RuntimeError, match="Live HTTP request blocked"):
        httpx.get("https://example.invalid/")
```

- [ ] **Step 3: Write failing model tests** — append to `tests/test_settings_amap.py`

```python
def test_geocode_and_route_result_models() -> None:
    from travel_assistant.models import GeocodeResult, RouteResult

    g = GeocodeResult(city="北京", country="中国", province="北京市",
                      adcode="110000", longitude=116.4, latitude=39.9)
    assert g.country == "中国"
    assert g.adcode == "110000"

    r = RouteResult(origin="A", destination="B", mode="driving",
                    distance_m=7995, duration_s=1233, provider="amap")
    assert r.provider == "amap"
    assert r.fallback_reason == ""

    f = RouteResult(origin="A", destination="B", mode="walking",
                    distance_m=500, duration_s=400, provider="mock-fallback",
                    fallback_reason="non-CN destination")
    assert f.provider == "mock-fallback"
    assert "non-CN" in f.fallback_reason
```

- [ ] **Step 4: Run the new test file → expect FAIL**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python -m pytest tests/test_settings_amap.py -q`
Expected: errors at collection or test failures (new fields/models/Protocols/guard absent).

- [ ] **Step 5: Bump `pyproject.toml`** — promote `httpx` to a direct dep and add `respx` as a dev dep.

In the `[project] dependencies = [...]` list, insert `"httpx==0.28.1"` in alphabetical position (kept exactly equal to the resolved version in M0). In `[project.optional-dependencies] dev = [...]`, add `"respx==0.22.0"`.

Final `dependencies` order (illustrative):
```
"httpx==0.28.1",
"langchain==1.3.1",
"langchain-core==1.4.0",
"langchain-deepseek==1.0.1",
"langgraph==1.2.0",
"langgraph-checkpoint-sqlite==2.0.10",
"pydantic==2.13.4",
"pydantic-settings==2.14.1",
"typer==0.23.1",
"click==8.1.8",
"tenacity==9.1.4",
```
Final `dev`:
```
"pytest==8.4.2", "respx==0.22.0", "ruff==0.15.13", "mypy==1.20.2", "pytest-cov==6.3.0"
```

> If `respx==0.22.0` does not resolve against `httpx==0.28.1`, report and adjust to the latest released `respx` compatible with `httpx==0.28.1` (do not silently unpin httpx). Note the resolved version in the commit.

- [ ] **Step 6: Re-run install**

Run: `make install`
Expected: clean resolve; new packages installed.

- [ ] **Step 7: Extend `src/travel_assistant/config.py`**

Append the new fields and extend `validated()`. The full updated file is:

```python
"""Application configuration loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_CHECKPOINTER_BACKENDS = {"memory", "sqlite"}
_VALID_PROVIDER_VALUES = {"mock", "amap"}
_PROVIDER_FIELDS: tuple[str, ...] = (
    "travel_agent_provider_poi",
    "travel_agent_provider_weather",
    "travel_agent_provider_route",
    "travel_agent_provider_geocoding",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # V0 fields (unchanged)
    deepseek_api_key: str | None = None
    travel_agent_model_id: str = "deepseek:deepseek-chat"
    travel_agent_fake_model: bool = False
    checkpointer_backend: str = "memory"
    travel_agent_sqlite_path: str = "data/checkpoints.sqlite3"
    travel_agent_prefs_path: str = "data/preferences.json"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None

    # V1 Amap additions
    amap_api_key: str | None = None
    amap_base_url: str = "https://restapi.amap.com/v3"
    travel_agent_provider_poi: str = "mock"
    travel_agent_provider_weather: str = "mock"
    travel_agent_provider_route: str = "mock"
    travel_agent_provider_geocoding: str = "mock"
    amap_request_timeout_s: float = 8.0
    amap_max_retries: int = 2
    amap_cache_max_entries: int = 256

    def validated(self) -> "Settings":
        if self.checkpointer_backend not in _VALID_CHECKPOINTER_BACKENDS:
            raise ValueError(
                "CHECKPOINTER_BACKEND must be one of "
                f"{sorted(_VALID_CHECKPOINTER_BACKENDS)}, got "
                f"{self.checkpointer_backend!r}"
            )
        for field in _PROVIDER_FIELDS:
            value = getattr(self, field)
            if value not in _VALID_PROVIDER_VALUES:
                raise ValueError(
                    f"{field.upper()} must be one of "
                    f"{sorted(_VALID_PROVIDER_VALUES)}, got {value!r}"
                )
        amap_selected = [
            f for f in _PROVIDER_FIELDS if getattr(self, f) == "amap"
        ]
        if amap_selected and not self.amap_api_key:
            raise ValueError(
                "AMAP_API_KEY is required when any of "
                f"{[f.upper() for f in amap_selected]} is set to 'amap'."
            )
        return self
```

- [ ] **Step 8: Extend `src/travel_assistant/models.py`**

Append two new models. Add to the top imports any items not already present (`datetime` is already imported). The additions go at the end of the file:

```python
class GeocodeResult(BaseModel):
    """Geocoding result. Note: Amap coordinates are GCJ-02."""

    city: str
    country: str
    province: str = ""
    adcode: str = ""
    longitude: float | None = None
    latitude: float | None = None


class RouteResult(BaseModel):
    """Route between two places.

    ``provider`` is ``"amap"`` for real Amap responses, ``"mock"`` for the
    deterministic mock, or ``"mock-fallback"`` when an Amap provider chose to
    delegate to its mock for a single call. ``fallback_reason`` is populated
    only when ``provider == "mock-fallback"``.
    """

    origin: str
    destination: str
    mode: str
    distance_m: int
    duration_s: int
    provider: str
    fallback_reason: str = ""
```

- [ ] **Step 9: Create the Protocols package**

`src/travel_assistant/providers/__init__.py`:
```python
"""Provider Protocols for V1. Implementations live in providers/mock and providers/amap."""
```

`src/travel_assistant/providers/poi.py`:
```python
"""POIProvider Protocol. Implementations: providers.mock.poi, providers.amap.poi."""
from typing import Protocol

from travel_assistant.models import Activity


class POIProvider(Protocol):
    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        ...
```

`src/travel_assistant/providers/weather.py`:
```python
"""WeatherProvider Protocol. Implementations: providers.mock.weather, providers.amap.weather."""
from typing import Protocol


class WeatherProvider(Protocol):
    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        ...
```

`src/travel_assistant/providers/route.py`:
```python
"""RouteProvider Protocol. Implementations: providers.mock.route, providers.amap.route."""
from typing import Protocol

from travel_assistant.models import RouteResult


class RouteProvider(Protocol):
    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        ...
```

`src/travel_assistant/providers/geocoding.py`:
```python
"""GeocodingProvider Protocol. Implementations: providers.mock.geocoding, providers.amap.geocoding."""
from typing import Protocol

from travel_assistant.models import GeocodeResult


class GeocodingProvider(Protocol):
    def geocode(self, city: str) -> GeocodeResult | None:
        ...
```

- [ ] **Step 10: Add live-HTTP guard to `tests/conftest.py`**

Replace the file with:
```python
import pytest


@pytest.fixture(autouse=True)
def _force_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_FAKE_MODEL", "true")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("AMAP_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _block_live_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defense in depth: any outbound httpx call not intercepted by respx
    raises a clear error. respx tests install their own MockTransport which
    overrides this guard for the duration of the respx scope."""
    import httpx

    def _deny(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError(
            "Live HTTP request blocked in tests. Use respx mocks or fix the "
            f"test. URL: {request.url!s}"
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _deny)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _deny)
```

> If `respx`'s patching does not stack cleanly over the monkeypatched transport (an empirical question first checked in M12), this fixture may need to be reordered to NOT apply when a test is wrapped in `@respx.mock`. The simplest fallback is to flip the guard from autouse to opt-in via `pytestmark = pytest.mark.usefixtures("block_live_http")` on test modules that need it. Verify in M12; adjust minimally and report.

- [ ] **Step 11: Extend `.env.example`** — append:

```
# V1 — Amap (real provider; opt-in)
AMAP_API_KEY=
AMAP_BASE_URL=https://restapi.amap.com/v3
TRAVEL_AGENT_PROVIDER_POI=mock
TRAVEL_AGENT_PROVIDER_WEATHER=mock
TRAVEL_AGENT_PROVIDER_ROUTE=mock
TRAVEL_AGENT_PROVIDER_GEOCODING=mock
AMAP_REQUEST_TIMEOUT_S=8.0
AMAP_MAX_RETRIES=2
AMAP_CACHE_MAX_ENTRIES=256
```

- [ ] **Step 12: Run the failing tests → green**

Run: `export PATH="$PWD/.venv/bin:$PATH" && python -m pytest tests/test_settings_amap.py -q`
Expected: all 5 tests pass.

- [ ] **Step 13: Run the full suite — no regressions**

Run: `python -m pytest -q && make lint type`
Expected: **77 prior + 5 new = 82 passed**; ruff/mypy clean.

- [ ] **Step 14: Commit M10**

```bash
git add pyproject.toml src/travel_assistant/config.py \
        src/travel_assistant/models.py src/travel_assistant/providers \
        .env.example tests/conftest.py tests/test_settings_amap.py
git commit -m "feat(v1-m10): foundations — deps, Settings, models, Protocols, live-HTTP guard"
```

**Acceptance:** all 82 tests pass; mypy/ruff clean; `Settings()` requires no `AMAP_API_KEY` for the default mock path; `Settings(travel_agent_provider_poi="amap")` without a key fails fast; the 4 Protocols import cleanly; an unintercepted `httpx.get(...)` raises the guard error.

**Risks:** `respx` version may not resolve against `httpx==0.28.1` — note and adjust. The live-HTTP guard may interact with `respx`'s patching in a non-obvious way — empirically verified in M12; documented fallback above. No regression risk to V0 because nothing in the V0 runtime path consults the new fields yet.

---

## Task 2 — M11: Mock providers (POI / Weather / Route / Geocoding)

**Goal:** Implement the four Mock providers as thin Protocol-conformant wrappers around V0's existing M2 pure functions, plus a new `mock_route_between` pure function and a small CN-city whitelist for `MockGeocodingProvider`. Existing V0 behavior is preserved exactly; provider tests assert Protocol conformance and the mock semantics that the Amap providers will rely on for fallback.

> ⚠️ Scope guard: this milestone is mock providers only. No factories (M16), no AmapHttpClient (M12), no Amap providers (M13–M15), no runtime_tools/runner changes (M16).

**Files:**
- Create: `src/travel_assistant/providers/mock/__init__.py`
- Create: `src/travel_assistant/providers/mock/poi.py`
- Create: `src/travel_assistant/providers/mock/weather.py`
- Create: `src/travel_assistant/providers/mock/route.py`
- Create: `src/travel_assistant/providers/mock/geocoding.py`
- Create: `src/travel_assistant/tools/route.py`
- Create: `tests/test_providers_mock.py`

- [ ] **Step 1: Write failing mock-provider tests** — `tests/test_providers_mock.py`

```python
from travel_assistant.models import (
    Activity,
    ComfortLevel,
    GeocodeResult,
    RouteResult,
)
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.mock.geocoding import MockGeocodingProvider
from travel_assistant.providers.mock.poi import MockPOIProvider
from travel_assistant.providers.mock.route import MockRouteProvider
from travel_assistant.providers.mock.weather import MockWeatherProvider
from travel_assistant.providers.poi import POIProvider
from travel_assistant.providers.route import RouteProvider
from travel_assistant.providers.weather import WeatherProvider


def test_mock_poi_protocol_and_determinism() -> None:
    p: POIProvider = MockPOIProvider()
    a = p.search("Tokyo", ["food"], seed=3)
    b = p.search("Tokyo", ["food"], seed=3)
    assert [x.model_dump() for x in a] == [x.model_dump() for x in b]
    assert any(isinstance(x, Activity) and x.category == "food" for x in a)


def test_mock_weather_protocol_and_determinism() -> None:
    p: WeatherProvider = MockWeatherProvider()
    assert p.forecast("Tokyo", 5, seed=2) == p.forecast("Tokyo", 5, seed=2)
    assert len(p.forecast("Tokyo", 5, seed=2)) == 5
    assert p.forecast("Tokyo", 0) == []


def test_mock_route_protocol_and_shape() -> None:
    p: RouteProvider = MockRouteProvider()
    r = p.route_between("Beijing", "Tianjin", "driving")
    assert isinstance(r, RouteResult)
    assert r.provider == "mock"
    assert r.distance_m > 0 and r.duration_s > 0
    assert r.mode == "driving"
    # determinism
    r2 = p.route_between("Beijing", "Tianjin", "driving")
    assert r2.model_dump() == r.model_dump()


def test_mock_route_invalid_mode_falls_back_to_driving() -> None:
    p = MockRouteProvider()
    r = p.route_between("A", "B", "unknown-mode")
    assert r.mode == "driving"


def test_mock_geocoding_cn_whitelist_and_unknown() -> None:
    p: GeocodingProvider = MockGeocodingProvider()
    g = p.geocode("北京")
    assert isinstance(g, GeocodeResult)
    assert g.country == "中国"
    assert g.adcode == "110000"
    assert p.geocode("Atlantis") is None  # unknown city -> None


def test_mock_geocoding_english_aliases() -> None:
    p = MockGeocodingProvider()
    assert p.geocode("Beijing") is not None
    assert p.geocode("beijing") is not None  # case-insensitive
    assert p.geocode("Shanghai") is not None
    assert p.geocode("Tokyo") is None  # not in CN whitelist
```

- [ ] **Step 2: Run → expect FAIL** (modules missing)

Run: `python -m pytest tests/test_providers_mock.py -q`
Expected: collection errors / ModuleNotFoundError.

- [ ] **Step 3: Implement `tools/route.py` (new M2-style pure mock)**

```python
"""Deterministic mock route helper (pure, used by MockRouteProvider)."""
import random

from travel_assistant.models import RouteResult

_VALID_MODES = ("driving", "walking", "transit", "bicycling")


def mock_route_between(
    origin: str, destination: str, mode: str = "driving", *, seed: int = 0
) -> RouteResult:
    """Return a deterministic mock RouteResult.

    Graceful edge handling: unknown mode falls back to ``"driving"``.
    Same args + seed -> identical output.
    """
    effective_mode = mode if mode in _VALID_MODES else "driving"
    o = origin.strip() or "unknown"
    d = destination.strip() or "unknown"
    rng = random.Random(f"route:{o.lower()}->{d.lower()}:{effective_mode}:{seed}")
    # Mode-specific bands (rough heuristics for a deterministic mock).
    bands = {
        "driving": (5_000, 50_000),
        "walking": (500, 8_000),
        "transit": (3_000, 40_000),
        "bicycling": (1_000, 20_000),
    }
    lo, hi = bands[effective_mode]
    distance_m = rng.randint(lo, hi)
    # average speed (m/s): driving 13, walking 1.3, transit 8, bicycling 4
    speed = {"driving": 13.0, "walking": 1.3, "transit": 8.0, "bicycling": 4.0}[
        effective_mode
    ]
    duration_s = int(distance_m / speed)
    return RouteResult(
        origin=o,
        destination=d,
        mode=effective_mode,
        distance_m=distance_m,
        duration_s=duration_s,
        provider="mock",
    )
```

- [ ] **Step 4: Implement the 4 mock providers**

`src/travel_assistant/providers/mock/__init__.py`:
```python
"""Mock providers — Protocol-conformant wrappers around V0 deterministic functions."""
from travel_assistant.providers.mock.geocoding import MockGeocodingProvider
from travel_assistant.providers.mock.poi import MockPOIProvider
from travel_assistant.providers.mock.route import MockRouteProvider
from travel_assistant.providers.mock.weather import MockWeatherProvider

__all__ = [
    "MockGeocodingProvider",
    "MockPOIProvider",
    "MockRouteProvider",
    "MockWeatherProvider",
]
```

`src/travel_assistant/providers/mock/poi.py`:
```python
from travel_assistant.models import Activity
from travel_assistant.tools.attractions import find_attractions


class MockPOIProvider:
    """Wraps tools.attractions.find_attractions."""

    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        return find_attractions(city, interests, seed=seed)
```

`src/travel_assistant/providers/mock/weather.py`:
```python
from travel_assistant.tools.weather import get_weather


class MockWeatherProvider:
    """Wraps tools.weather.get_weather."""

    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        return get_weather(city, days, seed=seed)
```

`src/travel_assistant/providers/mock/route.py`:
```python
from travel_assistant.models import RouteResult
from travel_assistant.tools.route import mock_route_between


class MockRouteProvider:
    """Wraps tools.route.mock_route_between."""

    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        return mock_route_between(origin, destination, mode)
```

`src/travel_assistant/providers/mock/geocoding.py` (small CN whitelist for offline determinism):
```python
from travel_assistant.models import GeocodeResult

# Minimal CN-city whitelist for offline tests / demos. Real Amap geocoding is
# used in production runs via providers.amap.geocoding.
_CN_CITIES: dict[str, GeocodeResult] = {
    "北京": GeocodeResult(
        city="北京", country="中国", province="北京市",
        adcode="110000", longitude=116.407526, latitude=39.904030,
    ),
    "上海": GeocodeResult(
        city="上海", country="中国", province="上海市",
        adcode="310000", longitude=121.473701, latitude=31.230416,
    ),
    "广州": GeocodeResult(
        city="广州", country="中国", province="广东省",
        adcode="440100", longitude=113.264385, latitude=23.129163,
    ),
    "杭州": GeocodeResult(
        city="杭州", country="中国", province="浙江省",
        adcode="330100", longitude=120.155070, latitude=30.274085,
    ),
}
_ALIASES: dict[str, str] = {
    "beijing": "北京",
    "shanghai": "上海",
    "guangzhou": "广州",
    "hangzhou": "杭州",
}


class MockGeocodingProvider:
    """Returns a deterministic GeocodeResult for known CN cities, else None."""

    def geocode(self, city: str) -> GeocodeResult | None:
        key = city.strip()
        if not key:
            return None
        if key in _CN_CITIES:
            return _CN_CITIES[key]
        alias = _ALIASES.get(key.lower())
        if alias:
            return _CN_CITIES[alias]
        return None
```

- [ ] **Step 5: Run → green**

Run: `python -m pytest tests/test_providers_mock.py -q && make lint type`
Expected: 6 new tests pass; ruff/mypy clean.

- [ ] **Step 6: Full suite — no regressions**

Run: `python -m pytest -q`
Expected: 82 prior + 6 new = **88 passed**.

- [ ] **Step 7: Commit M11**

```bash
git add src/travel_assistant/providers/mock src/travel_assistant/tools/route.py \
        tests/test_providers_mock.py
git commit -m "feat(v1-m11): mock providers (POI/Weather/Route/Geocoding)"
```

**Acceptance:** all 4 mock providers Protocol-conform; deterministic outputs; existing V0 behavior unchanged (M2 pure functions intact); 88 tests green; ruff/mypy clean.

**Risks:** None significant. Mock providers are thin pure wrappers; only the new `tools/route.py` is novel code, and it's covered.

---

## Task 3 — M12: `AmapHttpClient` (shared sync client + retry + LRU + redaction)

**Goal:** Build the single shared HTTP client every Amap provider will use. After this task: `AmapHttpClient.get(endpoint, params)` injects the API key, retries on 5xx + transient `httpx.HTTPError`, caches responses in an LRU, redacts the key in any log line, and never makes a real network call in tests (verified with respx).

> ⚠️ Scope guard: this is the client only. No provider classes that use it yet (those land in M13–M15).

**Files:**
- Create: `src/travel_assistant/providers/amap/__init__.py`
- Create: `src/travel_assistant/providers/amap/_errors.py`
- Create: `src/travel_assistant/providers/amap/_client.py`
- Create: `tests/test_providers_amap_client.py`

- [ ] **Step 1: Write failing client tests** — `tests/test_providers_amap_client.py`

```python
import logging

import httpx
import pytest
import respx

from travel_assistant.config import Settings
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import (
    AmapApiError,
    AmapTransientError,
)


def _settings() -> Settings:
    return Settings(
        amap_api_key="SECRET-KEY-123",
        amap_base_url="https://restapi.amap.com/v3",
        amap_request_timeout_s=2.0,
        amap_max_retries=2,
    )


@respx.mock
def test_get_injects_key_and_returns_json() -> None:
    route = respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200, json={"status": "1", "info": "OK", "geocodes": []}
        )
    )
    client = AmapHttpClient(_settings())
    data = client.get("geocode/geo", {"address": "Beijing"})

    assert data["status"] == "1"
    assert route.called
    sent_url = route.calls.last.request.url
    assert "key=SECRET-KEY-123" in str(sent_url)
    assert "output=JSON" in str(sent_url)


@respx.mock
def test_get_redacts_key_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})
    )
    caplog.set_level(logging.DEBUG, logger="travel_assistant.providers.amap")
    AmapHttpClient(_settings()).get("geocode/geo", {"address": "Beijing"})
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert "SECRET-KEY-123" not in full_log
    assert "key=***" in full_log or "key=REDACTED" in full_log


@respx.mock
def test_get_caches_repeated_call() -> None:
    route = respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})
    )
    client = AmapHttpClient(_settings())
    a = client.get("geocode/geo", {"address": "Beijing"})
    b = client.get("geocode/geo", {"address": "Beijing"})
    assert a == b
    assert route.call_count == 1  # second call served from cache


@respx.mock
def test_get_cache_miss_on_different_params() -> None:
    route = respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})
    )
    client = AmapHttpClient(_settings())
    client.get("geocode/geo", {"address": "Beijing"})
    client.get("geocode/geo", {"address": "Shanghai"})
    assert route.call_count == 2


@respx.mock
def test_retry_on_5xx_then_success() -> None:
    route = respx.get("https://restapi.amap.com/v3/place/text").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"status": "1", "info": "OK", "pois": []}),
        ]
    )
    client = AmapHttpClient(_settings())
    data = client.get("place/text", {"keywords": "x"})
    assert data["status"] == "1"
    assert route.call_count == 2


@respx.mock
def test_no_retry_on_4xx_raises() -> None:
    route = respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(400, text="bad request")
    )
    client = AmapHttpClient(_settings())
    with pytest.raises(AmapApiError):
        client.get("place/text", {"keywords": "x"})
    assert route.call_count == 1


@respx.mock
def test_persistent_5xx_eventually_raises_transient() -> None:
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(503)
    )
    with pytest.raises(AmapTransientError):
        AmapHttpClient(_settings()).get("place/text", {"keywords": "x"})


@respx.mock
def test_amap_status_not_1_raises_api_error() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200, json={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        )
    )
    with pytest.raises(AmapApiError, match="INVALID_USER_KEY"):
        AmapHttpClient(_settings()).get("geocode/geo", {"address": "Beijing"})
```

- [ ] **Step 2: Run → expect FAIL** (module missing)

Run: `python -m pytest tests/test_providers_amap_client.py -q`
Expected: ImportError on `travel_assistant.providers.amap._client`.

- [ ] **Step 3: Implement `_errors.py`**

`src/travel_assistant/providers/amap/_errors.py`:
```python
"""Typed Amap errors. Providers handle these uniformly."""


class AmapError(RuntimeError):
    """Base class for all Amap-related errors."""


class AmapTransientError(AmapError):
    """A transient upstream failure (network / 5xx) after retries are exhausted."""


class AmapApiError(AmapError):
    """A non-retryable upstream error (4xx, or Amap status != '1')."""


class AmapNotFoundError(AmapError):
    """An expected entity (e.g., geocode) was not found in Amap's response."""
```

- [ ] **Step 4: Implement `AmapHttpClient`**

`src/travel_assistant/providers/amap/__init__.py`:
```python
"""Amap real-data providers. Shared client + per-domain providers."""
```

`src/travel_assistant/providers/amap/_client.py`:
```python
"""Shared sync HTTP client for the Amap Web Service API.

Responsibilities:
- inject API key + output=JSON
- retry transient (5xx / httpx.HTTPError) up to settings.amap_max_retries
- in-memory LRU cache keyed on (endpoint, sorted non-key params)
- redact the API key in any log line via a single helper
- normalize errors to AmapApiError / AmapTransientError
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from travel_assistant.config import Settings
from travel_assistant.providers.amap._errors import (
    AmapApiError,
    AmapTransientError,
)

_LOG = logging.getLogger("travel_assistant.providers.amap")
_REDACTED = "***"


def _redact_key(text: str, key: str) -> str:
    if not key:
        return text
    return text.replace(key, _REDACTED)


class _RetryableHTTPError(Exception):
    """Internal marker so tenacity retries 5xx + httpx.HTTPError but not 4xx."""


class AmapHttpClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.amap_api_key or ""
        self._base = settings.amap_base_url.rstrip("/")
        self._timeout = settings.amap_request_timeout_s
        self._max_retries = settings.amap_max_retries
        self._cache: OrderedDict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = OrderedDict()
        self._cache_cap = settings.amap_cache_max_entries
        self._client = httpx.Client(timeout=self._timeout)

    # ----- public ---------------------------------------------------------
    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        cache_key = (endpoint, tuple(sorted((k, str(v)) for k, v in params.items())))
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            _LOG.debug("amap cache HIT endpoint=%s", endpoint)
            return self._cache[cache_key]

        try:
            data = self._get_with_retry(endpoint, params)
        except RetryError as e:
            raise AmapTransientError(
                f"Amap upstream failed after retries: endpoint={endpoint}"
            ) from e

        # Amap-level errors: status != "1" => non-retryable API error
        status = data.get("status")
        if status != "1":
            info = data.get("info", "")
            infocode = data.get("infocode", "")
            raise AmapApiError(
                f"Amap API error endpoint={endpoint} info={info} infocode={infocode}"
            )

        # cache and return
        self._cache[cache_key] = data
        if len(self._cache) > self._cache_cap:
            self._cache.popitem(last=False)
        _LOG.debug("amap cache MISS endpoint=%s stored", endpoint)
        return data

    # ----- internal -------------------------------------------------------
    def _get_with_retry(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        attempts = self._max_retries + 1
        decorated = retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.2, max=2.0),
            retry=retry_if_exception_type(_RetryableHTTPError),
            reraise=True,
        )(self._do_get)
        return decorated(endpoint, params)

    def _do_get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}/{endpoint}"
        full_params = {**params, "key": self._key, "output": "JSON"}
        try:
            resp = self._client.get(url, params=full_params)
        except httpx.HTTPError as e:
            self._log_with_redaction(
                logging.WARNING, "amap http error endpoint=%s url=%s err=%s",
                endpoint, url, str(e),
            )
            raise _RetryableHTTPError(str(e)) from e

        # Log endpoint + status (redacted URL)
        self._log_with_redaction(
            logging.DEBUG, "amap call endpoint=%s status=%s url=%s",
            endpoint, resp.status_code, _redact_key(str(resp.url), self._key),
        )

        if 500 <= resp.status_code < 600:
            raise _RetryableHTTPError(f"5xx status={resp.status_code}")
        if 400 <= resp.status_code < 500:
            raise AmapApiError(
                f"Amap 4xx endpoint={endpoint} status={resp.status_code}"
            )
        try:
            return resp.json()
        except ValueError as e:
            raise AmapApiError(
                f"Amap non-JSON response endpoint={endpoint}"
            ) from e

    def _log_with_redaction(self, level: int, fmt: str, *args: Any) -> None:
        if not _LOG.isEnabledFor(level):
            return
        # Redact in pre-formatted message so even raw key in args is scrubbed.
        msg = fmt % args
        _LOG.log(level, _redact_key(msg, self._key))
```

> mypy notes: `OrderedDict[...]` typing may need adjustment depending on installed mypy strictness; reduce to `OrderedDict[tuple[str, tuple], dict[str, object]]` if needed.

- [ ] **Step 5: Run client tests → green**

Run: `python -m pytest tests/test_providers_amap_client.py -q`
Expected: 8 tests pass.

> Verify here that `respx` properly overrides the conftest live-HTTP guard. If the guard blocks respx, adjust the conftest fixture (e.g., only deny when `respx.MockRouter` has not been entered) and re-run. Report any change made.

- [ ] **Step 6: Lint/type + full suite**

Run: `make lint type && python -m pytest -q`
Expected: 88 prior + 8 new = **96 passed**.

- [ ] **Step 7: Commit M12**

```bash
git add src/travel_assistant/providers/amap tests/test_providers_amap_client.py
git commit -m "feat(v1-m12): AmapHttpClient (sync httpx + retry + LRU + redaction)"
```

**Acceptance:** all client tests pass with respx; key is never leaked into logs; cache hits avoid duplicate calls; 5xx triggers retry, 4xx raises `AmapApiError`, Amap `status!="1"` raises `AmapApiError`; persistent 5xx raises `AmapTransientError`.

**Risks:** respx + autouse live-HTTP guard interaction (resolve empirically as noted in Step 5). `tenacity`+`httpx` exception mapping nuance (covered by tests). `OrderedDict` typing under mypy (adjust if needed).

---

## Task 4 — M13: Amap Geocoding provider

**Goal:** Implement `AmapGeocodingProvider.geocode(city)` returning a populated `GeocodeResult` for in-CN matches and `None` for unknown / non-CN / malformed responses.

**Files:**
- Create: `src/travel_assistant/providers/amap/geocoding.py`
- Create: `tests/test_providers_amap_geocoding.py`

- [ ] **Step 1: Write failing geocoding tests** — `tests/test_providers_amap_geocoding.py`

```python
import httpx
import respx

from travel_assistant.config import Settings
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_RESP = {
    "status": "1",
    "info": "OK",
    "infocode": "10000",
    "count": "1",
    "geocodes": [
        {
            "country": "中国",
            "province": "北京市",
            "city": [],
            "adcode": "110000",
            "location": "116.407526,39.904030",
        }
    ],
}

_EMPTY_RESP = {"status": "1", "info": "OK", "count": "0", "geocodes": []}


@respx.mock
def test_cn_city_returns_geocode_result() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_RESP)
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    g = p.geocode("北京")
    assert g is not None
    assert g.country == "中国"
    assert g.adcode == "110000"
    assert g.longitude == 116.407526
    assert g.latitude == 39.904030


@respx.mock
def test_empty_geocodes_returns_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_EMPTY_RESP)
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    assert p.geocode("Atlantis") is None


@respx.mock
def test_non_cn_country_returns_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "count": "1",
                "geocodes": [
                    {
                        "country": "日本",
                        "province": "東京都",
                        "city": [],
                        "adcode": "",
                        "location": "139.6917,35.6895",
                    }
                ],
            },
        )
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    assert p.geocode("Tokyo") is None  # outside CN coverage -> None per spec §8


@respx.mock
def test_malformed_response_returns_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})  # no geocodes key
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    assert p.geocode("X") is None


@respx.mock
def test_api_error_is_swallowed_to_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200, json={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        )
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    # Geocoding is "soft": upstream API error -> None so callers can fall back.
    assert p.geocode("北京") is None
```

- [ ] **Step 2: Run → expect FAIL** (module missing)

Run: `python -m pytest tests/test_providers_amap_geocoding.py -q`
Expected: ImportError.

- [ ] **Step 3: Implement geocoding provider**

`src/travel_assistant/providers/amap/geocoding.py`:
```python
"""AmapGeocodingProvider: returns GeocodeResult or None (soft)."""
from __future__ import annotations

import logging

from travel_assistant.models import GeocodeResult
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError

_LOG = logging.getLogger("travel_assistant.providers.amap.geocoding")


class AmapGeocodingProvider:
    def __init__(self, client: AmapHttpClient) -> None:
        self._client = client

    def geocode(self, city: str) -> GeocodeResult | None:
        key = city.strip()
        if not key:
            return None
        try:
            data = self._client.get("geocode/geo", {"address": key})
        except AmapError as e:
            _LOG.info("amap geocoding soft-fail city=%s err=%s", key, type(e).__name__)
            return None

        codes = data.get("geocodes") or []
        if not codes:
            return None
        first = codes[0]
        country = (first.get("country") or "").strip()
        if country != "中国":
            return None
        adcode = (first.get("adcode") or "").strip()
        province = (first.get("province") or "").strip()
        location = (first.get("location") or "").strip()
        lng: float | None = None
        lat: float | None = None
        if "," in location:
            try:
                lng_s, lat_s = location.split(",", 1)
                lng = float(lng_s)
                lat = float(lat_s)
            except ValueError:
                lng = None
                lat = None
        return GeocodeResult(
            city=key,
            country=country,
            province=province,
            adcode=adcode,
            longitude=lng,
            latitude=lat,
        )
```

- [ ] **Step 4: Run → green; full suite no-regression**

Run: `python -m pytest tests/test_providers_amap_geocoding.py -q && python -m pytest -q && make lint type`
Expected: 5 new pass; 96 + 5 = **101 passed**; ruff/mypy clean.

- [ ] **Step 5: Commit M13**

```bash
git add src/travel_assistant/providers/amap/geocoding.py \
        tests/test_providers_amap_geocoding.py
git commit -m "feat(v1-m13): AmapGeocodingProvider (CN-only, soft-fail to None)"
```

**Acceptance:** CN city → populated `GeocodeResult`; empty/non-CN/malformed/upstream-error → `None` (soft). Tests cover all five paths.

**Risks:** Amap's real geocoding response fields can vary (e.g., `city` is sometimes a list, sometimes a string); the malformed-response test covers the missing-key path. Real-world coordinate parsing edge cases are tolerated (return None for lng/lat only, GeocodeResult still returned if country is CN).

---

## Task 5 — M14: Amap POI and Weather providers (with per-call non-CN fallback)

**Goal:** Implement `AmapPOIProvider.search(...)` and `AmapWeatherProvider.forecast(...)`. Both depend on an injected `GeocodingProvider` (to detect non-CN cities) and an injected mock counterpart (to fall back per call). Tests cover the CN happy path and the non-CN fallback path, asserting the fallback log line.

**Files:**
- Create: `src/travel_assistant/providers/amap/poi.py`
- Create: `src/travel_assistant/providers/amap/weather.py`
- Create: `tests/test_providers_amap_poi.py`
- Create: `tests/test_providers_amap_weather.py`

- [ ] **Step 1: Write failing POI tests** — `tests/test_providers_amap_poi.py`

```python
import logging

import httpx
import pytest
import respx

from travel_assistant.config import Settings
from travel_assistant.models import Activity
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.poi import AmapPOIProvider
from travel_assistant.providers.mock.poi import MockPOIProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "北京市", "adcode": "110000",
                  "location": "116.4,39.9"}],
}
_POI_RESP = {
    "status": "1", "info": "OK", "count": "2",
    "pois": [
        {"id": "1", "name": "故宫博物院", "type": "风景名胜",
         "typecode": "110200", "address": "景山前街4号", "location": "116.4,39.9"},
        {"id": "2", "name": "南锣鼓巷", "type": "风景名胜",
         "typecode": "110200", "address": "鼓楼地区", "location": "116.4,39.9"},
    ],
}


@respx.mock
def test_cn_city_uses_amap_path() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_GEO)
    )
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(200, json=_POI_RESP)
    )
    client = AmapHttpClient(_settings())
    p = AmapPOIProvider(
        client=client,
        geocoding=AmapGeocodingProvider(client),
        fallback=MockPOIProvider(),
    )
    result = p.search("北京", ["city walks"])
    assert all(isinstance(a, Activity) for a in result)
    assert any("故宫" in a.name for a in result)


@respx.mock
def test_non_cn_city_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK", "count": "0", "geocodes": []})
    )
    # No expectation on /place/text — must NOT be called for non-CN.
    client = AmapHttpClient(_settings())
    p = AmapPOIProvider(
        client=client,
        geocoding=AmapGeocodingProvider(client),
        fallback=MockPOIProvider(),
    )
    caplog.set_level(logging.INFO, logger="travel_assistant.providers.amap")
    result = p.search("Tokyo", ["food"])
    assert len(result) >= 1                                # mock always returns something
    assert any("falling back to mock" in r.getMessage() for r in caplog.records)


@respx.mock
def test_amap_upstream_error_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_GEO)
    )
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(503)
    )
    client = AmapHttpClient(_settings())
    p = AmapPOIProvider(
        client=client,
        geocoding=AmapGeocodingProvider(client),
        fallback=MockPOIProvider(),
    )
    caplog.set_level(logging.INFO, logger="travel_assistant.providers.amap")
    result = p.search("北京", ["food"])
    assert len(result) >= 1
    assert any("falling back to mock" in r.getMessage() for r in caplog.records)
```

- [ ] **Step 2: Write failing Weather tests** — `tests/test_providers_amap_weather.py`

```python
import logging

import httpx
import pytest
import respx

from travel_assistant.config import Settings
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.weather import AmapWeatherProvider
from travel_assistant.providers.mock.weather import MockWeatherProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "北京市", "adcode": "110000",
                  "location": "116.4,39.9"}],
}
_WX = {
    "status": "1", "info": "OK",
    "forecasts": [{
        "city": "北京市", "adcode": "110000",
        "casts": [
            {"date": "2026-06-01", "dayweather": "晴", "nightweather": "多云"},
            {"date": "2026-06-02", "dayweather": "多云", "nightweather": "晴"},
            {"date": "2026-06-03", "dayweather": "小雨", "nightweather": "阴"},
        ],
    }],
}


@respx.mock
def test_cn_city_uses_amap_forecast() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_GEO)
    )
    respx.get("https://restapi.amap.com/v3/weather/weatherInfo").mock(
        return_value=httpx.Response(200, json=_WX)
    )
    client = AmapHttpClient(_settings())
    p = AmapWeatherProvider(client, AmapGeocodingProvider(client), MockWeatherProvider())
    out = p.forecast("北京", 3)
    assert out == ["晴", "多云", "小雨"]


@respx.mock
def test_non_cn_city_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK", "count": "0", "geocodes": []})
    )
    client = AmapHttpClient(_settings())
    p = AmapWeatherProvider(client, AmapGeocodingProvider(client), MockWeatherProvider())
    caplog.set_level(logging.INFO, logger="travel_assistant.providers.amap")
    out = p.forecast("Paris", 5)
    assert len(out) == 5  # mock honors `days`
    assert any("falling back to mock" in r.getMessage() for r in caplog.records)
```

- [ ] **Step 3: Run both test files → expect FAIL** (modules missing)

Run: `python -m pytest tests/test_providers_amap_poi.py tests/test_providers_amap_weather.py -q`

- [ ] **Step 4: Implement `AmapPOIProvider`**

`src/travel_assistant/providers/amap/poi.py`:
```python
"""AmapPOIProvider — per-call mock fallback for non-CN / upstream errors."""
from __future__ import annotations

import logging
from typing import Any

from travel_assistant.models import Activity
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.poi import POIProvider

_LOG = logging.getLogger("travel_assistant.providers.amap.poi")

# Narrow interest -> Amap POI category (typecode) mapping for V1. Other
# interests fall through to keyword search.
_INTEREST_TYPES: dict[str, str] = {
    "food": "050000",
    "city walks": "110000",
    "history": "110200",
}


class AmapPOIProvider:
    def __init__(
        self,
        client: AmapHttpClient,
        geocoding: GeocodingProvider,
        fallback: POIProvider,
    ) -> None:
        self._client = client
        self._geo = geocoding
        self._fallback = fallback

    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        geo = self._geo.geocode(city)
        if geo is None or geo.country != "中国" or not geo.adcode:
            _LOG.info(
                "[amap] city=%s outside CN coverage; falling back to mock for this call",
                city,
            )
            return self._fallback.search(city, interests, seed=seed)

        try:
            return self._search_amap(city, geo.adcode, interests)
        except AmapError as e:
            _LOG.info(
                "[amap] city=%s upstream error (%s); falling back to mock for this call",
                city, type(e).__name__,
            )
            return self._fallback.search(city, interests, seed=seed)

    def _search_amap(
        self, city: str, adcode: str, interests: list[str]
    ) -> list[Activity]:
        effective = [i for i in interests if i.strip()] or ["sightseeing"]
        seen_ids: set[str] = set()
        out: list[Activity] = []
        for interest in effective:
            params: dict[str, Any] = {
                "city": adcode,
                "citylimit": "true",
                "offset": "5",
                "page": "1",
            }
            typecode = _INTEREST_TYPES.get(interest.lower())
            if typecode:
                params["types"] = typecode
            else:
                params["keywords"] = interest
            data = self._client.get("place/text", params)
            for poi in data.get("pois") or []:
                pid = str(poi.get("id") or poi.get("name"))
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                name = (poi.get("name") or "").strip()
                if not name:
                    continue
                category = interest if typecode else "sightseeing"
                out.append(
                    Activity(
                        name=f"{name} ({city})",
                        category=category,
                        notes=(poi.get("address") or "").strip(),
                    )
                )
        return out
```

- [ ] **Step 5: Implement `AmapWeatherProvider`**

`src/travel_assistant/providers/amap/weather.py`:
```python
"""AmapWeatherProvider — per-call mock fallback for non-CN / upstream errors."""
from __future__ import annotations

import logging

from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.weather import WeatherProvider

_LOG = logging.getLogger("travel_assistant.providers.amap.weather")


class AmapWeatherProvider:
    def __init__(
        self,
        client: AmapHttpClient,
        geocoding: GeocodingProvider,
        fallback: WeatherProvider,
    ) -> None:
        self._client = client
        self._geo = geocoding
        self._fallback = fallback

    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        if days <= 0:
            return []
        geo = self._geo.geocode(city)
        if geo is None or geo.country != "中国" or not geo.adcode:
            _LOG.info(
                "[amap] city=%s outside CN coverage; falling back to mock for this call",
                city,
            )
            return self._fallback.forecast(city, days, seed=seed)
        try:
            data = self._client.get(
                "weather/weatherInfo", {"city": geo.adcode, "extensions": "all"}
            )
        except AmapError as e:
            _LOG.info(
                "[amap] city=%s upstream error (%s); falling back to mock for this call",
                city, type(e).__name__,
            )
            return self._fallback.forecast(city, days, seed=seed)

        forecasts = data.get("forecasts") or []
        if not forecasts:
            _LOG.info(
                "[amap] city=%s empty forecast; falling back to mock for this call",
                city,
            )
            return self._fallback.forecast(city, days, seed=seed)
        casts = forecasts[0].get("casts") or []
        out = [(c.get("dayweather") or "").strip() for c in casts[:days] if c.get("dayweather")]
        # If Amap returns fewer days than requested, pad with mock for the
        # remaining days (rare; explicit per spec §8 "graceful").
        if len(out) < days:
            extra = self._fallback.forecast(city, days - len(out), seed=seed)
            out.extend(extra)
        return out
```

- [ ] **Step 6: Run new tests → green; full suite no-regression**

Run: `python -m pytest tests/test_providers_amap_poi.py tests/test_providers_amap_weather.py -q && python -m pytest -q && make lint type`
Expected: 3 + 2 = 5 new pass; 101 + 5 = **106 passed**; ruff/mypy clean.

- [ ] **Step 7: Commit M14**

```bash
git add src/travel_assistant/providers/amap/poi.py \
        src/travel_assistant/providers/amap/weather.py \
        tests/test_providers_amap_poi.py tests/test_providers_amap_weather.py
git commit -m "feat(v1-m14): AmapPOIProvider + AmapWeatherProvider with non-CN fallback"
```

**Acceptance:** CN city + interests → real-shaped `Activity` list / weather list; non-CN city → mock fallback with explicit log; upstream error → mock fallback; empty result → mock fallback.

**Risks:** Amap POI response field naming variations (`pois` empty/missing, `id` collisions) — covered with defensive defaults. Weather field naming (`dayweather`) — covered.

---

## Task 6 — M15: Amap Route provider + RouteResult provenance

**Goal:** Implement `AmapRouteProvider.route_between(origin, destination, mode)` returning a `RouteResult` with `provider="amap"` for CN routes, `provider="mock-fallback"` with populated `fallback_reason` for non-CN routes / upstream errors / unsupported modes.

**Files:**
- Create: `src/travel_assistant/providers/amap/route.py`
- Create: `tests/test_providers_amap_route.py`

- [ ] **Step 1: Write failing route tests** — `tests/test_providers_amap_route.py`

```python
import httpx
import respx

from travel_assistant.config import Settings
from travel_assistant.models import RouteResult
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.route import AmapRouteProvider
from travel_assistant.providers.mock.route import MockRouteProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "北京市", "adcode": "110000",
                  "location": "116.481028,39.989643"}],
}
_TJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "天津市", "adcode": "120000",
                  "location": "117.190182,39.125596"}],
}
_DRIVING = {
    "status": "1", "info": "OK", "count": "1",
    "route": {
        "origin": "116.481028,39.989643", "destination": "117.190182,39.125596",
        "paths": [{"distance": "137995", "duration": "9233", "steps": []}],
    },
}


@respx.mock
def test_cn_route_returns_amap_provider() -> None:
    geo = respx.get("https://restapi.amap.com/v3/geocode/geo")
    geo.mock(side_effect=[
        httpx.Response(200, json=_BJ_GEO),
        httpx.Response(200, json=_TJ_GEO),
    ])
    respx.get("https://restapi.amap.com/v3/direction/driving").mock(
        return_value=httpx.Response(200, json=_DRIVING)
    )
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("北京", "天津", "driving")
    assert isinstance(r, RouteResult)
    assert r.provider == "amap"
    assert r.distance_m == 137995
    assert r.duration_s == 9233
    assert r.mode == "driving"


@respx.mock
def test_non_cn_origin_or_destination_falls_back() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK", "count": "0", "geocodes": []})
    )
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("Paris", "Lyon", "driving")
    assert r.provider == "mock-fallback"
    assert "non-CN" in r.fallback_reason or "outside CN" in r.fallback_reason


@respx.mock
def test_upstream_error_falls_back_with_reason() -> None:
    geo = respx.get("https://restapi.amap.com/v3/geocode/geo")
    geo.mock(side_effect=[
        httpx.Response(200, json=_BJ_GEO),
        httpx.Response(200, json=_TJ_GEO),
    ])
    respx.get("https://restapi.amap.com/v3/direction/driving").mock(
        return_value=httpx.Response(503)
    )
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("北京", "天津", "driving")
    assert r.provider == "mock-fallback"
    assert "upstream" in r.fallback_reason.lower()


def test_unsupported_mode_falls_back_locally() -> None:
    # No HTTP calls expected.
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("北京", "天津", "teleport")
    assert r.provider == "mock-fallback"
    assert "mode" in r.fallback_reason.lower()
```

- [ ] **Step 2: Run → expect FAIL** (module missing)

Run: `python -m pytest tests/test_providers_amap_route.py -q`

- [ ] **Step 3: Implement `AmapRouteProvider`**

`src/travel_assistant/providers/amap/route.py`:
```python
"""AmapRouteProvider — RouteResult with `provider` provenance + fallback."""
from __future__ import annotations

import logging

from travel_assistant.models import RouteResult
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.route import RouteProvider

_LOG = logging.getLogger("travel_assistant.providers.amap.route")

_MODE_ENDPOINT: dict[str, str] = {
    "driving": "direction/driving",
    "walking": "direction/walking",
    "transit": "direction/transit/integrated",
    "bicycling": "direction/bicycling",
}


class AmapRouteProvider:
    def __init__(
        self,
        client: AmapHttpClient,
        geocoding: GeocodingProvider,
        fallback: RouteProvider,
    ) -> None:
        self._client = client
        self._geo = geocoding
        self._fallback = fallback

    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        if mode not in _MODE_ENDPOINT:
            return self._mock_with_reason(
                origin, destination, mode, f"unsupported mode {mode!r}"
            )
        o_geo = self._geo.geocode(origin)
        d_geo = self._geo.geocode(destination)
        if (
            o_geo is None
            or d_geo is None
            or o_geo.country != "中国"
            or d_geo.country != "中国"
            or o_geo.longitude is None
            or o_geo.latitude is None
            or d_geo.longitude is None
            or d_geo.latitude is None
        ):
            return self._mock_with_reason(
                origin, destination, mode, "non-CN or unresolvable endpoint(s)"
            )
        try:
            data = self._client.get(
                _MODE_ENDPOINT[mode],
                {
                    "origin": f"{o_geo.longitude},{o_geo.latitude}",
                    "destination": f"{d_geo.longitude},{d_geo.latitude}",
                },
            )
        except AmapError as e:
            return self._mock_with_reason(
                origin, destination, mode, f"upstream error: {type(e).__name__}"
            )

        route = data.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            return self._mock_with_reason(
                origin, destination, mode, "empty paths"
            )
        first = paths[0]
        try:
            distance_m = int(first.get("distance"))
            duration_s = int(first.get("duration"))
        except (TypeError, ValueError):
            return self._mock_with_reason(
                origin, destination, mode, "malformed paths"
            )
        return RouteResult(
            origin=origin,
            destination=destination,
            mode=mode,
            distance_m=distance_m,
            duration_s=duration_s,
            provider="amap",
        )

    def _mock_with_reason(
        self, origin: str, destination: str, mode: str, reason: str
    ) -> RouteResult:
        _LOG.info(
            "[amap] route %s->%s mode=%s falling back to mock: %s",
            origin, destination, mode, reason,
        )
        m = self._fallback.route_between(origin, destination, mode)
        return RouteResult(
            origin=m.origin,
            destination=m.destination,
            mode=m.mode,
            distance_m=m.distance_m,
            duration_s=m.duration_s,
            provider="mock-fallback",
            fallback_reason=reason,
        )
```

- [ ] **Step 4: Run → green; full suite no-regression**

Run: `python -m pytest tests/test_providers_amap_route.py -q && python -m pytest -q && make lint type`
Expected: 4 new pass; 106 + 4 = **110 passed**; ruff/mypy clean.

- [ ] **Step 5: Commit M15**

```bash
git add src/travel_assistant/providers/amap/route.py tests/test_providers_amap_route.py
git commit -m "feat(v1-m15): AmapRouteProvider with provenance + fallback_reason"
```

**Acceptance:** CN endpoints → `provider="amap"` with non-zero distance/duration; any non-CN, unsupported mode, upstream error, or malformed response → `provider="mock-fallback"` + `fallback_reason` populated.

**Risks:** Amap `direction/*` response shape mildly varies by mode (transit has multiple paths/segments); V1 reads `paths[0].distance/duration` which is correct for driving/walking/bicycling. Transit may require special handling — flagged but covered by the upstream-error/empty-paths fallback; a future ticket can enrich transit handling without changing the Provider interface.

---

## Task 7 — M16: Factories + `build_tools(settings)` + `route_between` tool

**Goal:** Add the four `get_*_provider(settings)` factories, change `build_tools` to take `settings` and wire providers via factories, add the new `@tool route_between` to the agent's tool list, and update `Runner` to pass `settings` through. After this task: the agent can call `route_between` end-to-end via a scripted fake test; default `Settings()` still produces an all-mock runtime.

**Files:**
- Modify: `src/travel_assistant/providers/poi.py` (add factory)
- Modify: `src/travel_assistant/providers/weather.py` (add factory)
- Modify: `src/travel_assistant/providers/route.py` (add factory)
- Modify: `src/travel_assistant/providers/geocoding.py` (add factory)
- Modify: `src/travel_assistant/tools/runtime_tools.py`
- Modify: `src/travel_assistant/runner.py`
- Modify: `tests/test_runtime_tools.py`

- [ ] **Step 1: Add factories to the 4 Protocol modules**

For each module, append a `get_*_provider(settings)` factory. Pattern (shown for POI; mirror for the others):

`src/travel_assistant/providers/poi.py` (append):
```python
def get_poi_provider(settings):  # type: ignore[no-untyped-def]
    """Return the POIProvider selected by settings. Mock is the default."""
    settings.validated()
    from travel_assistant.providers.mock.poi import MockPOIProvider

    mock = MockPOIProvider()
    if settings.travel_agent_provider_poi == "amap":
        from travel_assistant.providers.amap._client import AmapHttpClient
        from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
        from travel_assistant.providers.amap.poi import AmapPOIProvider

        client = AmapHttpClient(settings)
        return AmapPOIProvider(client, AmapGeocodingProvider(client), mock)
    return mock
```

`src/travel_assistant/providers/weather.py` (append): same shape with `MockWeatherProvider` + `AmapWeatherProvider`.

`src/travel_assistant/providers/route.py` (append): same shape with `MockRouteProvider` + `AmapRouteProvider`.

`src/travel_assistant/providers/geocoding.py` (append): same shape with `MockGeocodingProvider` + `AmapGeocodingProvider`. (Standalone — no fallback parameter; geocoding returns `None` on failure.)

- [ ] **Step 2: Update `runtime_tools.py`**

Change `build_tools(store, user_id)` to `build_tools(store, user_id, settings)`. Replace direct M2 calls with provider calls. Add the `route_between` tool. Full updated function (only the changed parts):

```python
from travel_assistant.config import Settings
from travel_assistant.providers.poi import get_poi_provider
from travel_assistant.providers.route import get_route_provider
from travel_assistant.providers.weather import get_weather_provider


def build_tools(store: PreferenceStore, user_id: str, settings: Settings) -> list[Any]:
    poi = get_poi_provider(settings)
    wx = get_weather_provider(settings)
    route_p = get_route_provider(settings)

    @tool
    def record_trip_request(...):  # unchanged
        ...

    @tool
    def search_flights_tool(runtime: ToolRuntime) -> list[dict[str, Any]]:
        """Search flights for the recorded trip."""
        tr = _trip_request(runtime)
        return [f.model_dump() for f in flights.search_flights(tr.origin or "", tr.destination or "")]

    @tool
    def search_hotels_tool(runtime: ToolRuntime) -> list[dict[str, Any]]:
        """Search hotels for the recorded trip."""
        tr = _trip_request(runtime)
        return [h.model_dump() for h in hotels.search_hotels(tr.destination or "", tr.comfort_level or ComfortLevel.COMFORT)]

    @tool
    def get_weather_tool(runtime: ToolRuntime) -> list[str]:
        """Get a weather outlook for the destination."""
        tr = _trip_request(runtime)
        return wx.forecast(tr.destination or "", tr.duration_days or 3)

    @tool
    def find_attractions_tool(runtime: ToolRuntime) -> list[dict[str, Any]]:
        """Find attractions matching the traveler's interests."""
        tr = _trip_request(runtime)
        return [a.model_dump() for a in poi.search(tr.destination or "", tr.interests)]

    @tool
    def estimate_budget_tool(runtime: ToolRuntime) -> dict[str, Any]:
        """Estimate the trip budget from the recorded trip."""
        tr = _trip_request(runtime)
        fl = flights.search_flights(tr.origin or "", tr.destination or "")
        ho = hotels.search_hotels(tr.destination or "", tr.comfort_level or ComfortLevel.COMFORT)
        return budget.estimate_budget(fl, ho, tr.duration_days or 3, tr.party_size).model_dump()

    @tool
    def route_between(
        runtime: ToolRuntime, origin: str, destination: str, mode: str = "driving"
    ) -> dict[str, Any]:
        """Compute time and distance between two places (Amap or mock)."""
        _ = runtime  # silence ToolRuntime injection
        return route_p.route_between(origin, destination, mode).model_dump()

    @tool
    def save_preference(...):  # unchanged
        ...

    return [
        record_trip_request,
        search_flights_tool,
        search_hotels_tool,
        get_weather_tool,
        find_attractions_tool,
        estimate_budget_tool,
        route_between,            # NEW
        save_preference,
    ]
```

Imports to add at the top of `runtime_tools.py`: `from travel_assistant.config import Settings`, the 3 factories above.

- [ ] **Step 3: Update `runner.py`** — pass `settings` through

In `Runner.run`, change the call:
```python
tools = (
    self._tools_override
    if self._tools_override is not None
    else build_tools(self._store, user_id)        # OLD
)
```
to:
```python
tools = (
    self._tools_override
    if self._tools_override is not None
    else build_tools(self._store, user_id, self._settings)
)
```

Add `self._settings: Settings` to `Runner.__init__` (new field). In `build_runner`, also pass `settings` into the Runner:
```python
return Runner(model, store, tools, InMemorySaver() if settings.checkpointer_backend == "memory" else make_checkpointer(settings), settings)
```
(keep existing checkpointer factory call; just thread `settings` in).

- [ ] **Step 4: Update / add tests** — `tests/test_runtime_tools.py`

Append a scripted-fake integration test exercising `route_between`:
```python
def _route_call(cid: str, args: dict | None = None) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "route_between", "args": args or {
            "origin": "北京", "destination": "天津", "mode": "driving"
        }, "id": cid}],
    )


def test_route_between_default_mock(tmp_path: Path) -> None:
    runner = build_runner(
        _settings(tmp_path),
        scripted_fake_messages=[
            _record_call("c1"),
            _route_call("c2"),
            _tripplan_call(),
        ],
    )
    r = runner.run("u1", "t1", "plan it")
    assert any(
        isinstance(m, ToolMessage) and '"provider": "mock"' in str(m.content)
        for m in r.messages
    )
    assert isinstance(r.plan, TripPlan)
```

If any existing test calls `build_tools(store, user_id)` with the OLD signature, update them in lockstep to pass `settings` (e.g., `Settings(travel_agent_fake_model=True)`).

- [ ] **Step 5: Run full suite — no regressions**

Run: `python -m pytest -q && make lint type`
Expected: 110 + 1 (new route_between scripted test) = **111 passed**; ruff/mypy clean.

> If a previously-existing test (e.g., a build_tools-based unit) breaks on signature change, update it in lockstep (no behavior change). Do NOT relax the new signature back to old.

- [ ] **Step 6: Commit M16**

```bash
git add src/travel_assistant/providers/{poi,weather,route,geocoding}.py \
        src/travel_assistant/tools/runtime_tools.py src/travel_assistant/runner.py \
        tests/test_runtime_tools.py
git commit -m "feat(v1-m16): factories + build_tools(settings) + route_between tool"
```

**Acceptance:** default `Settings()` → all-mock runtime; `Settings(travel_agent_provider_poi="amap", amap_api_key="k")` → `AmapPOIProvider`; `route_between` is callable end-to-end by the scripted fake agent; 111 tests pass; mypy/ruff clean.

**Risks:** `build_tools` signature change cascades to tests — fix in lockstep, do not silently restore the old API. Lazy imports in factories are needed to avoid a circular import between `providers.poi` and `providers.amap.poi`.

---

## Task 8 — M17: README polish + V1 Definition of Done

**Goal:** Make the project's surface match V1. Update the README with the new env table rows, the Amap section, the per-call non-CN fallback note, the demo recipe, and a pointer to the V1 spec/plan. Confirm `make ci` green and all the spec's V1 DoD criteria.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Extend the README env table**

Append to the existing env table in `README.md`:
```markdown
| `AMAP_API_KEY` | _(none)_ | Required only when any `TRAVEL_AGENT_PROVIDER_*=amap`; not needed for default mock runs |
| `AMAP_BASE_URL` | `https://restapi.amap.com/v3` | Amap base URL (rarely overridden) |
| `TRAVEL_AGENT_PROVIDER_POI` | `mock` | `mock` (default) or `amap` |
| `TRAVEL_AGENT_PROVIDER_WEATHER` | `mock` | `mock` or `amap` |
| `TRAVEL_AGENT_PROVIDER_ROUTE` | `mock` | `mock` or `amap` |
| `TRAVEL_AGENT_PROVIDER_GEOCODING` | `mock` | `mock` or `amap` |
| `AMAP_REQUEST_TIMEOUT_S` | `8.0` | httpx timeout per Amap call |
| `AMAP_MAX_RETRIES` | `2` | tenacity retries on 5xx / transient errors |
| `AMAP_CACHE_MAX_ENTRIES` | `256` | in-process LRU cache size |
```

- [ ] **Step 2: Add the V1 Amap section** (insert after `## Long-term memory`)

```markdown
---

## V1 — Amap (高德地图) integration

Real-data providers for POI, weather, route, and geocoding via the Amap Web
Service API. Mock providers remain the default; Amap is opt-in.

**Enable Amap for a domain:**
\`\`\`bash
export AMAP_API_KEY=...                 # obtain from https://lbs.amap.com
export TRAVEL_AGENT_PROVIDER_POI=amap
export TRAVEL_AGENT_PROVIDER_WEATHER=amap
export TRAVEL_AGENT_PROVIDER_ROUTE=amap
export TRAVEL_AGENT_PROVIDER_GEOCODING=amap
\`\`\`

**Per-call non-CN fallback:** Amap coverage is strongest for Chinese cities.
For cities outside CN (e.g., Tokyo, Paris) or upstream errors, the Amap
provider transparently falls back to the deterministic mock for that single
call and logs the reason. `RouteResult.provider` is set to `"mock-fallback"`
with `fallback_reason` populated in that case.

**The new `route_between` tool** is exposed to the agent and returns
`{origin, destination, mode, distance_m, duration_s, provider, fallback_reason}`.

**No real API calls in tests.** Unit tests use `respx` to mock httpx, and a
conftest fixture blocks any unintercepted outbound request. `AMAP_API_KEY` is
deleted from the test environment.

See `docs/superpowers/specs/2026-05-20-v1-amap-integration-design.md` (spec)
and `docs/superpowers/plans/2026-05-20-v1-amap-integration.md` (plan).
```

(Note: render literal triple backticks; the `\`\`\`` above is just escape for this plan file.)

- [ ] **Step 3: Update the roadmap section bullets**

Replace the `## Roadmap` body with:
```markdown
**Completed milestones:**
- V0 — M0 scaffold · M1 models · M2 tools · M3 memory · M4 LLM layer · M5 agent core · M6 ToolRuntime/Command · M7 short-term memory · M8 streaming/CLI · M9 tracing + polish.
- V1 — M10 foundations · M11 mock providers · M12 AmapHttpClient · M13 geocoding · M14 POI+weather · M15 route · M16 wiring · M17 docs.

**Post-V1 cleanup:**
- **CL-1** — sqlite serde pin alignment (see `docs/superpowers/plans/2026-05-18-travel-assistant-agent.md`, Post-M9 section).

**v2 roadmap:** see `docs/roadmap/travel-assistant-v1-v3-roadmap.md`.
```

- [ ] **Step 4: Full CI gate**

Run: `make ci`
Expected: lint + type + **111 tests passed**.

- [ ] **Step 5: V1 DoD checklist (manual)**

Verify against the spec §17 DoD:
- [ ] Default `Settings()` selects mock providers everywhere; demos and V0 tests unchanged.
- [ ] `TRAVEL_AGENT_PROVIDER_*=amap` + `AMAP_API_KEY` produces real Amap data for CN cities; non-CN falls back per call with a log line.
- [ ] Missing `AMAP_API_KEY` while any `*=amap` → fail-fast at startup.
- [ ] `route_between` exposed and exercised by a scripted test.
- [ ] `AMAP_API_KEY` never appears in logs (covered by `test_get_redacts_key_in_logs`).
- [ ] `make ci` green; total test count = V0's 77 + V1 new tests.
- [ ] README documents env vars, mock-default policy, and the non-CN fallback.

- [ ] **Step 6: Commit M17**

```bash
git add README.md
git commit -m "docs(v1-m17): README polish + V1 DoD; full make ci green"
```

**Acceptance:** README accurately reflects V1; `make ci` green; all DoD items checked.

**Risks:** README drift between text and code (mitigated by linking the spec/plan and the env table being derived from the actual `Settings` field list).

---

## Plan Self-Review

**Spec coverage:**
- §1 goal → all 8 tasks collectively.
- §2 baseline & deps → Task 1.
- §3 architecture → Task 6 (factories + build_tools wiring), Tasks 3–6 (providers).
- §4 settings → Task 1.
- §5 Protocols → Task 1.
- §6 `AmapHttpClient` → Task 3.
- §7 cache & retry → Task 3.
- §8 non-CN fallback → Tasks 5, 6 (each Amap provider).
- §9 new models → Task 1 (declared); §9.3 `Activity` unchanged → no task touches it (by design).
- §10 endpoints → Task 3 (client URLs), Tasks 4–6 (each provider).
- §11 file structure → matches Tasks 1–7.
- §12 `build_tools` change → Task 7.
- §13 error handling → Task 3 (client errors) + Tasks 5–6 (provider fallbacks).
- §14 testing strategy → every task's tests + Task 1 (conftest guard) + Task 3 (respx tests).
- §15 milestones → Tasks 1–8 ≡ M10–M17.
- §16 risks → reflected in each task's `Risks` block.
- §17 DoD → Task 8 Step 5 checklist.
- §18 out of scope → respected; no task touches flights/hotels real APIs, async, disk cache, quota cap, cassettes, multi-agent, web, BaseStore, CL-1, or `Activity` schema.

No spec requirement is left without a task.

**Placeholder scan:** no "TBD/TODO-as-deferral"; every step shows the actual code/command/expected output. The two empirical notes (M0 step 5 dep-resolution check, M12 step 5 respx-vs-conftest-guard verification) describe a concrete action with a clear next step on failure — not deferred work.

**Type consistency:** `GeocodeResult`/`RouteResult` field names identical across Tasks 1, 4, 5, 6; provider method signatures (`search`, `forecast`, `route_between`, `geocode`) identical across Protocol declarations (Task 1), mock impls (Task 2), Amap impls (Tasks 4–6), and tool wrappers (Task 7); `build_tools(store, user_id, settings)` signature stable from Task 7 onward; factory names `get_{poi,weather,route,geocoding}_provider` consistent across Task 7 and Task 6's wiring; `provider` literal values `"mock" | "amap" | "mock-fallback"` are the only ones produced anywhere.

**Fixes applied inline:** none required; the plan tracks the spec faithfully and the spec's intentional ambiguities (e.g., transit-mode response handling) are explicitly acknowledged with the fallback path as the safety net.
