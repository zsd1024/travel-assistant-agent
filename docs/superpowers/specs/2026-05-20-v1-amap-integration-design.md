# V1 — Amap Web Service Integration

- **Date:** 2026-05-20
- **Status:** Approved design (pre-implementation)
- **Architecture choice:** Approach A — Tight V1, Provider `Protocol` + factory behind the unchanged V0 tool surface
- **Builds on:** V0 spec (`docs/superpowers/specs/2026-05-18-travel-assistant-agent-design.md`), API spike findings (`docs/superpowers/notes/api-spike-findings.md`), V1–V3 roadmap (`docs/roadmap/travel-assistant-v1-v3-roadmap.md`)

## 1. Goal

Integrate the **Amap (高德地图) Web Service APIs** as opt-in real-data providers for POI, weather, route, and geocoding, behind the existing V0 tool surface. Mock providers remain the default offline path; CI never makes a real API call; `AMAP_API_KEY` is never logged or committed. A new `route_between` tool is added and wired into `build_tools`.

### Non-goals (V1)

- Real flight/hotel providers (defer to V1.5 / V2).
- Async `httpx` client (sync only; revisit in V2 for fan-out).
- Persistent disk cache (in-memory LRU only).
- Per-run Amap quota cap (revisit if abuse observed).
- Real-API integration tests in CI (would require `AMAP_API_KEY`; not in V1).
- Multi-agent reshape, web UI, `BaseStore` migration (V2/V3).
- DeepSeek live structured-output verification (separate small task; tracked in roadmap §13).
- Recorded HTTP cassettes (`vcrpy` and similar) — explicitly rejected; see §14.
- Schema changes to `Activity` (no provider/provenance fields added in V1; see §9.3).

## 2. Tech baseline & dependency additions

| Dep | Status | Role |
|---|---|---|
| `httpx` | **Promote transitive → direct** (already installed as a langchain transitive) | Sync HTTP client for Amap |
| `respx` | **Add (dev)** | Programmatic `httpx` mocks; synthetic Amap JSON responses for unit tests |

No other dependency additions. No version bumps required for the V0 pin set.

## 3. Architecture overview

```
runtime_tools.build_tools(store, user_id, settings)
        │
        ├── find_attractions_tool  ──→  get_poi_provider(settings)       ──→  MockPOIProvider | AmapPOIProvider
        ├── get_weather_tool       ──→  get_weather_provider(settings)   ──→  MockWeatherProvider | AmapWeatherProvider
        ├── route_between_tool     ──→  get_route_provider(settings)     ──→  MockRouteProvider | AmapRouteProvider
        ├── (geocoding internal)   ──→  get_geocoding_provider(settings) ──→  MockGeocodingProvider | AmapGeocodingProvider
        └── (record_trip_request, save_preference, estimate_budget, search_flights, search_hotels — unchanged)
                                                                    │
              ┌─────────────────────────────────────────────────────┤
              ▼                                                     ▼
      MockProvider (V0 M2 pure functions, unchanged)         AmapProvider(s) ──→ AmapHttpClient (shared)
                                                                                          │
                                                                                  auth + retry + LRU cache + key redaction
```

- **Tools call providers, never the HTTP layer directly.**
- **Mock providers are unchanged V0 functions wrapped in the Protocol.** Zero behavioural change in default/CI mode.
- **Each Amap provider holds a reference to its mock counterpart** as a per-call fallback (injected by the factory).
- **One shared `AmapHttpClient`** centralizes `httpx` config, headers, retry, cache, logging, and key redaction.

## 4. Settings additions (`src/travel_assistant/config.py`)

```python
amap_api_key: str | None = None
amap_base_url: str = "https://restapi.amap.com/v3"
travel_agent_provider_poi: str = "mock"        # "mock" | "amap"
travel_agent_provider_weather: str = "mock"    # "mock" | "amap"
travel_agent_provider_route: str = "mock"      # "mock" | "amap"
travel_agent_provider_geocoding: str = "mock"  # "mock" | "amap"  (internal; tied to others)
amap_request_timeout_s: float = 8.0
amap_max_retries: int = 2
amap_cache_max_entries: int = 256
```

Env vars (pydantic-settings maps automatically; case-insensitive):

| Env var | Maps to |
|---|---|
| `AMAP_API_KEY` | `amap_api_key` |
| `AMAP_BASE_URL` | `amap_base_url` |
| `TRAVEL_AGENT_PROVIDER_POI` | `travel_agent_provider_poi` |
| `TRAVEL_AGENT_PROVIDER_WEATHER` | `travel_agent_provider_weather` |
| `TRAVEL_AGENT_PROVIDER_ROUTE` | `travel_agent_provider_route` |
| `TRAVEL_AGENT_PROVIDER_GEOCODING` | `travel_agent_provider_geocoding` |
| `AMAP_REQUEST_TIMEOUT_S` | `amap_request_timeout_s` |
| `AMAP_MAX_RETRIES` | `amap_max_retries` |
| `AMAP_CACHE_MAX_ENTRIES` | `amap_cache_max_entries` |

`Settings.validated()` is extended to:

1. Reject any `travel_agent_provider_*` value not in `{"mock", "amap"}` (clear `ValueError`).
2. **Fail-fast on missing key:** if **any** `travel_agent_provider_*` is `"amap"` and `amap_api_key` is empty/None → raise a clear `ValueError` mentioning `AMAP_API_KEY` and the providers that need it. **Missing key is never a silent fallback** when the user explicitly opted into Amap (this mirrors V0's `ModelConfigError` for `DEEPSEEK_API_KEY`).
3. Default config (all providers `"mock"`) imposes **no `AMAP_API_KEY` requirement** — pure offline path keeps working out of the box.

`.env.example` adds the new keys with sensible defaults (`AMAP_API_KEY=` blank; all `TRAVEL_AGENT_PROVIDER_*=mock`). The README env table is extended in lockstep.

## 5. Provider Protocols (`src/travel_assistant/providers/`)

```python
# providers/poi.py
from typing import Protocol
from travel_assistant.models import Activity

class POIProvider(Protocol):
    def search(self, city: str, interests: list[str], *, seed: int = 0) -> list[Activity]: ...

# providers/weather.py
class WeatherProvider(Protocol):
    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]: ...

# providers/route.py
from travel_assistant.models import RouteResult  # NEW model (see §9)

class RouteProvider(Protocol):
    def route_between(self, origin: str, destination: str, mode: str = "driving") -> RouteResult: ...

# providers/geocoding.py
from travel_assistant.models import GeocodeResult  # NEW model

class GeocodingProvider(Protocol):
    def geocode(self, city: str) -> GeocodeResult | None: ...   # None if not found / no coverage
```

All Protocols mirror their existing tool signatures — **no agent-facing tool signature changes** for the existing tools. Tests assert the Amap implementations are structurally compatible with the Protocols (same pattern as the M3 `PreferenceStore` test).

## 6. Amap shared HTTP client (`providers/amap/_client.py`)

A small typed sync class with these responsibilities:

- Compose URL = `{amap_base_url}/{endpoint}`; inject `key={amap_api_key}` and `output=JSON`.
- `httpx.Client(timeout=settings.amap_request_timeout_s)`.
- Retry via `tenacity` (already pinned) on transient `httpx.HTTPError` + 5xx responses; **never** retry on 4xx (treated as user/config error).
- In-memory LRU cache keyed by `(endpoint, sorted(non-key params)) → JSON response`, capacity = `amap_cache_max_entries`. The API key is **not** part of the cache key.
- Logging: **redact `key=...`** in any logged URL via a single helper used everywhere the client formats URLs; log endpoint + status + cache hit/miss; response bodies only at DEBUG level.
- Errors normalize to `AmapApiError` / `AmapTransientError` / `AmapNotFoundError` for providers to handle uniformly.

## 7. Cache & retry

- **Cache scope:** per-process LRU. No persistence. (Same query → same response within a run; mirrors V0 M2 determinism in spirit.)
- **TTL:** none in V1. Cache is cleared when the process exits.
- **Retry:** at most `amap_max_retries=2` exponential backoffs, capped at ~2 s. Transient errors only.
- **Idempotence:** all five Amap endpoints we use are GET / safe.

## 8. Non-CN fallback policy

Implemented uniformly across Amap providers:

1. Provider entrypoint (e.g., `AmapPOIProvider.search(city, interests, ...)`) first asks its injected `GeocodingProvider` for `geocode(city)`.
2. If `GeocodeResult` is `None` OR `country != "中国"` OR `adcode` is empty → the provider logs `[amap] city=<X> outside CN coverage; falling back to mock for this call` and **delegates to its injected mock provider** for that single call, returning the mock result. Where the return type supports it (`RouteResult`, `GeocodeResult`), `provider="mock-fallback"` is set with a `fallback_reason`.
3. Otherwise the provider issues its Amap call(s) and returns real data with `provider="amap"` where applicable.

Runtime Amap upstream errors (network failure, `AmapTransientError` after retry, `AmapApiError`, empty result for the destination) → **same per-call mock fallback path** with `fallback_reason` reflecting the cause. The agent loop never sees a raw `httpx` exception.

The fallback is **per call**, not a global flag — the agent can hit Amap for some destinations and mock for others within the same run. Tests cover both legs explicitly.

## 9. New data models (`src/travel_assistant/models.py`)

### 9.1 `GeocodeResult`

```python
class GeocodeResult(BaseModel):
    city: str
    country: str                 # e.g. "中国" for CN matches
    province: str = ""
    adcode: str                  # Amap admin region code; "" if unknown
    longitude: float | None = None
    latitude: float | None = None  # Amap returns GCJ-02 coordinates; documented in docstring
```

### 9.2 `RouteResult`

```python
class RouteResult(BaseModel):
    origin: str
    destination: str
    mode: str                    # "driving" | "walking" | "transit" | "bicycling"
    distance_m: int              # meters
    duration_s: int              # seconds
    provider: str                # "mock" | "amap" | "mock-fallback"
    fallback_reason: str = ""    # populated when provider == "mock-fallback"
```

Matches the explicit field list (origin, destination, mode, distance, duration, provider, fallback metadata).

### 9.3 `Activity` schema is unchanged

V1 **does not** add provider or provenance fields to `Activity`. For POI results, fallback provenance is observable via logs and per-test provider assertions — *not* via the data model. If a future UI surface needs per-item provenance, the metadata schema change is deferred to V2/V3.

## 10. Amap endpoints used

| Provider | Endpoint | Purpose |
|---|---|---|
| Geocoding | `GET /v3/geocode/geo` (+ `/regeo`) | city → `(country, province, adcode, lng, lat)` |
| POI | `GET /v3/place/text` (+ `/place/around`) | POI by keyword + city/adcode + category |
| Route | `GET /v3/direction/driving` / `/walking` / `/transit/integrated` / `/bicycling` | distance + duration |
| Weather | `GET /v3/weather/weatherInfo` (`extensions=all`) | live + 3-day forecast by adcode |

The interest → Amap POI category mapping table lives in `providers/amap/poi.py` (e.g., `food → 050000`, `city walks → 110000`; default to keyword search). Documented at the top of the file, intentionally narrow for V1.

## 11. File structure (new files only)

```
src/travel_assistant/
├── providers/
│   ├── __init__.py
│   ├── poi.py                # POIProvider Protocol + get_poi_provider(settings)
│   ├── weather.py            # WeatherProvider Protocol + factory
│   ├── route.py              # RouteProvider Protocol + factory
│   ├── geocoding.py          # GeocodingProvider Protocol + factory
│   ├── mock/
│   │   ├── __init__.py
│   │   ├── poi.py            # MockPOIProvider — wraps existing tools.attractions
│   │   ├── weather.py        # wraps tools.weather
│   │   ├── route.py          # NEW MockRouteProvider (deterministic, seeded)
│   │   └── geocoding.py      # NEW MockGeocodingProvider (CN whitelist for tests)
│   └── amap/
│       ├── __init__.py
│       ├── _client.py        # AmapHttpClient (shared sync httpx)
│       ├── _errors.py
│       ├── poi.py
│       ├── weather.py
│       ├── route.py
│       └── geocoding.py
src/travel_assistant/tools/runtime_tools.py   # MODIFIED: route_between_tool; tools use factories
src/travel_assistant/tools/route.py           # NEW M2-style mock pure fn (used by MockRouteProvider)
src/travel_assistant/config.py                # MODIFIED: new Settings fields + validated()
src/travel_assistant/models.py                # MODIFIED: add GeocodeResult, RouteResult
.env.example                                  # MODIFIED: new keys
README.md                                     # MODIFIED: env table + Amap section
tests/conftest.py                             # MODIFIED: live-HTTP guard (see §14)
tests/test_providers_mock.py                  # NEW — Protocol conformance + mock semantics
tests/test_providers_amap_client.py           # NEW — respx tests for shared client
tests/test_providers_amap_geocoding.py
tests/test_providers_amap_poi.py              # incl. non-CN fallback
tests/test_providers_amap_weather.py
tests/test_providers_amap_route.py
tests/test_runtime_tools.py                   # MODIFIED — add route_between scripted test
tests/test_settings_amap.py                   # NEW — validated() fail-fast + provider-switch behavior
```

Existing `tools/{attractions,weather,flights,hotels,budget}.py` are **unchanged** (they remain the deterministic substrate that `MockPOIProvider` / `MockWeatherProvider` wrap).

## 12. `build_tools` change

`build_tools(store, user_id, settings)` gains the `settings` argument. Internally:

```python
poi   = get_poi_provider(settings)
wx    = get_weather_provider(settings)
route = get_route_provider(settings)
```

`find_attractions_tool` and `get_weather_tool` delegate to the providers instead of calling the M2 pure functions directly. A new `@tool route_between(runtime: ToolRuntime, origin: str, destination: str, mode: str = "driving") -> dict[str, Any]` returns `RouteResult.model_dump()`. `Runner` passes `settings` through to `build_tools`.

This is a minor breaking change to `build_tools`' signature — the `Runner` is the only caller and is updated in lockstep. Tests that previously called `build_tools(store, user_id)` are updated.

## 13. Error handling

- **Config errors** (no key with `amap` selected, unknown provider value) → raised by `Settings.validated()` at startup, before any tool runs.
- **Amap HTTP errors:** retried transiently, then surfaced as `AmapApiError` to the provider. Each provider catches its own errors and falls back to the mock for that call (with a clear log + `provider="mock-fallback"` where the return type supports it). The agent loop never sees a raw `httpx` exception.
- **Empty results** (geocoding returns no match, POI search returns `[]`) → treated as a legitimate empty result; provider falls back to mock for that call rather than handing the agent an empty list it cannot reason about.
- **Key redaction** is owned by `AmapHttpClient` (§6); not restated here to avoid duplication.

## 14. Testing strategy

- **`MockProvider` conformance:** unit tests assert mock implementations are structurally compatible with the Protocols (mypy + runtime spot checks). Existing V0 M2 functions remain unchanged.
- **`AmapHttpClient` (respx):** key/`output=JSON` appended, redacted in logs (assert no leaked key in caplog); retry on 5xx and `httpx.HTTPError`; no retry on 4xx; LRU cache hit on second identical call; cache miss on different params.
- **`AmapGeocodingProvider` (respx):** CN city → populated `GeocodeResult`; non-CN city → `None`; malformed response → `None`.
- **`AmapPOIProvider` (respx):** CN city + interests → real-shaped `Activity` list with `provider="amap"` observable via logs / provider-state, **not** via the `Activity` model; non-CN city → mock fallback path, returns mock result, fallback log line asserted.
- **`AmapWeatherProvider` (respx):** CN city forecast for N days; non-CN city → mock fallback.
- **`AmapRouteProvider` (respx):** CN endpoints → `RouteResult(provider="amap", distance_m>0, duration_s>0)`; non-CN endpoints → `provider="mock-fallback"` with populated `fallback_reason`.
- **`route_between` tool integration (scripted fake agent):** script `record_trip_request → route_between(call) → TripPlan` (3 scripted messages); assert `RouteResult`-shaped `ToolMessage`.
- **Settings/provider-switch tests:** `Settings(travel_agent_provider_poi="amap", amap_api_key="x").validated()` → `AmapPOIProvider`; default `Settings()` → `MockPOIProvider`; `Settings(travel_agent_provider_poi="amap", amap_api_key=None).validated()` → clear `ValueError` mentioning `AMAP_API_KEY`; unknown provider value → `ValueError`.
- **Synthetic JSON only.** All Amap responses in tests are short, hand-written JSON literals declared in the test file. **No HTTP cassettes are committed** (no `vcrpy`, no recorded fixtures); the test suite has no recorded-API artifact directory.
- **Live-HTTP guard:** `tests/conftest.py` is extended with an autouse fixture that fails any test attempting an outbound `httpx` request not intercepted by `respx`. `AMAP_API_KEY` is also explicitly deleted from the environment by `conftest.py` so no test can accidentally pick up a real key. Defense in depth.
- **CI gate:** `make ci` stays green with the new tests; the 77 V0 tests must remain unchanged (no regression).

## 15. Milestones

Each milestone ends with concrete acceptance criteria; the detailed Task-by-Task implementation plan is produced separately via the writing-plans skill.

| # | Milestone | Acceptance criteria |
|---|---|---|
| **M10** | Foundations: `Settings` additions; `.validated()` extended; `.env.example` updated; `conftest.py` live-HTTP guard; empty `providers/` package skeleton | Default `Settings()` requires no `AMAP_API_KEY` and still passes `.validated()`; any `amap` provider without key fails `.validated()` with a clear message; unknown provider value rejected; conftest blocks accidental live HTTP |
| **M11** | Mock providers (POI, Weather, Route, Geocoding) wrapping existing V0 functions / a new mock route helper; Protocol-conformance tests | All 4 mock impls satisfy their Protocols (mypy + runtime); existing V0 behavior unchanged; 77 prior tests still green |
| **M12** | `AmapHttpClient` + `_errors.py`: shared sync client, retry, LRU cache, key redaction | respx tests cover auth, retry-on-5xx, no-retry-on-4xx, cache hit/miss, redacted logging |
| **M13** | `AmapGeocodingProvider` | respx tests: CN city populates `GeocodeResult`; non-CN city returns `None` |
| **M14** | `AmapPOIProvider` + `AmapWeatherProvider` (incl. per-call mock fallback) | respx tests: CN city uses Amap path; non-CN city falls back to mock with the asserted log line |
| **M15** | `AmapRouteProvider` + `RouteResult` model + `MockRouteProvider` | `provider` field is `"amap"` for CN, `"mock-fallback"` for non-CN/empty/upstream-error with `fallback_reason` populated |
| **M16** | Factories + `build_tools(store, user_id, settings)` + new `route_between` tool wired; `Runner` updated | Default settings → all mock providers; explicit `amap` settings → Amap providers; scripted agent test (`record_trip_request → route_between → TripPlan`) green |
| **M17** | Docs + DoD: README env table, Amap section, non-CN policy, demo recipe; final polish | `make ci` green; V0's 77 tests + V1 new tests all pass; no real API calls anywhere in CI |

## 16. Risks & mitigations

- **Amap reachability / quota / IP region from non-CN reviewers** → mock default + per-call fallback + cache + clear docs; offline test suite never calls the network.
- **GCJ-02 vs WGS84 coordinate mismatch** → V1 stores coords exactly as returned by Amap (GCJ-02 in `GeocodeResult`); model docstring is explicit; no conversion in V1 (revisit if V3 mixes providers).
- **`build_tools` signature change** → only `Runner` calls it; tests updated in lockstep; documented in §12.
- **Cache obscures auth/config changes** → cache lives within the process; restarting clears it. Documented.
- **Dependency drift (httpx promoted to direct; respx added)** → pinned exactly like the V0 stack; no other pin movement; CI re-verifies.
- **Misuse of real key in tests** → autouse `delenv` of `AMAP_API_KEY` + conftest live-HTTP guard; verified by a test that asserts an unintercepted call fails.
- **V0 spec §13 carry-forward (DeepSeek strategy unverified)** is *not* addressed by V1 directly; tracked separately.
- **CL-1 (sqlite serde pin alignment)** remains tracked and orthogonal; V1 does not start it.

## 17. V1 Definition of Done

- Default `Settings()` selects mock providers for all four domains; all V0 demos and tests work unchanged.
- Setting `TRAVEL_AGENT_PROVIDER_POI=amap` (etc.) + `AMAP_API_KEY` produces real Amap data for CN cities; non-CN cities transparently fall back per call with a log line.
- Selecting any `amap` provider without `AMAP_API_KEY` fails fast at startup with a clear error.
- `route_between` is exposed to the agent and exercised by a scripted test.
- `AMAP_API_KEY` is never present in logs (verified by a redaction test).
- `make ci` green; total test count = V0's 77 + the new V1 provider/settings/integration tests; no regressions.
- README documents env vars, the mock-default policy, and the non-CN fallback.

## 18. Out of scope for V1 (deferred)

- Flights/hotels real APIs.
- Async / concurrent `httpx` (V2).
- Disk-persistent cache; per-run Amap quota cap.
- LangSmith trace assertions on Amap calls.
- Multi-agent reshape (V2); web UI (V3); `BaseStore` migration (V3).
- Recorded HTTP cassettes (explicitly rejected).
- `Activity` provider/provenance schema changes (deferred to V2/V3 if a UI needs them).
- CL-1 (still tracked; orthogonal).
