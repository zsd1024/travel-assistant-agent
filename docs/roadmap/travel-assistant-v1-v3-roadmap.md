# Travel Assistant Agent — V1 / V2 / V3 Roadmap (Design Only)

- **Date:** 2026-05-20
- **Status:** Draft — discussion / pre-implementation reference
- **Scope:** Documentation only. No source code, dependency, or CL-1 changes implied. Each version below will get its own dedicated spec + plan before any implementation begins.
- **Companion docs:** `docs/superpowers/specs/2026-05-18-travel-assistant-agent-design.md` (V0 design), `docs/superpowers/plans/2026-05-18-travel-assistant-agent.md` (V0 plan, incl. CL-1 post-M9 cleanup), `docs/superpowers/notes/api-spike-findings.md` (LangChain 1.x API findings).

---

## 1. Current V0 positioning

**What V0 is.** A single-agent, CLI-first travel-planning **engineering reference implementation** of LangChain 1.x `create_agent` + LangGraph patterns: `ToolRuntime`/`Command` state, structured Pydantic output (`TripPlan`), checkpointer + `thread_id` short-term memory, JSON long-term preference store, deterministic offline-runnable fake model, streaming CLI, optional LangSmith tracing, full type/lint/test gate (77 tests).

**What V0 is not.** Not a production travel app, not a real-data planner, not multi-tenant, not networked. The domain tools are deterministic mocks; the agent is one ReAct loop.

**Primary purpose of V0.** Interview-ready, GitHub-public demonstration of clean LangChain/LangGraph engineering. Future versions productize it; V0 remains the **engineering substrate** — its tool/runner/state/checkpointer/preference interfaces are the contracts later versions consume.

**Open carry-forward from V0.** CL-1 (sqlite serde pin alignment; the `_MetadataSerde` shim removal) — tracked in the V0 plan, non-blocking, deliberately deferred.

---

## 2. V1 goals — real API integration

**One-line goal.** Replace selected mock tools with real-data providers (primarily **Amap / 高德地图**) behind the same tool interfaces, so the agent plans against real POIs / routes / weather while preserving the offline fake-model path.

**Concrete V1 deliverables.**
- An Amap web-service client (typed, retried, rate-limit-aware, cached).
- `find_attractions` backed by Amap POI search (with categories/keywords from the trip's interests).
- `get_weather` backed by Amap weather.
- A new `route_between(origin, destination, mode)` tool surfacing time/distance for itinerary composition.
- Geocoding helper (`city → adcode/coords`) used internally by the above.
- Provider abstraction so each tool has a `mock` and `amap` implementation, selected via settings (`PROVIDER_POI=amap|mock`, etc.).
- Graceful fallback: missing API key or upstream failure → degrade to mock with a clear log entry; the run still completes.
- Cassette/recorded-fixture tests (e.g., `vcrpy`) for the Amap path so CI stays offline.
- Documented setup (Amap key acquisition, regional caveats).

**Explicit V1 non-goals.** Real flight/hotel providers (complex, regulated, business-account heavy — defer to V1.5 / V2). Web UI. Multi-agent rework.

---

## 3. V2 goals — multi-agent LangGraph system

**One-line goal.** Re-architect from a single ReAct agent into an **explicit `StateGraph` of specialized agents** coordinated by a supervisor, exercising LangGraph's deeper features (typed shared state, parallel branches, conditional edges, sub-graphs, interrupts).

**Why now (after V1, not in V1).** Real data makes the planning problem decomposable in meaningful ways (research vs logistics vs budget vs composition). Multi-agent without real data is theatre.

**Concrete V2 deliverables.**
- A redesigned `TravelAgentState` shared across agents (additive — not replacing the M1 models; the structured `TripPlan` remains the output).
- A `StateGraph` with named nodes for each specialized agent and a supervisor/router node, with conditional edges and parallel fan-out/fan-in.
- Per-agent prompts, tools, and tests (each agent independently runnable with a scripted fake).
- Bounded-clarification primitive (`decide_clarification`) finally **wired** into an intake sub-graph (closes the V0 carry-forward note about it being tested but not yet enforced in `src/`).
- Post-model preference extraction (closes V0 spec §14 v2 item) — automatic learning of durable preferences from completed trips.
- Critic loop with revision budget.
- Comprehensive observability (LangSmith encouraged in dev).

**Explicit V2 non-goals.** Web UI (V3). Real flight/hotel data (still optional). Distributed deployment.

---

## 4. V3 goals — web product

**One-line goal.** Productize V2 as a **web app**: FastAPI backend exposing the multi-agent graph over HTTP/SSE, React frontend with conversational chat + Amap map visualization + itinerary editing + preferences + auth.

**Concrete V3 deliverables.**
- Backend: FastAPI service with session/thread endpoints, streaming agent endpoint, plans/preferences CRUD, auth, Postgres persistence, OpenTelemetry / LangSmith observability, Docker deployment.
- LangGraph checkpointer migrated from sqlite to Postgres (durable, multi-process).
- Long-term preference store migrated from JSON to LangGraph `BaseStore` over Postgres (closes the M3 `UPGRADE.md` path described in the V0 spec).
- Frontend: React + TypeScript SPA — chat panel with streaming, day-by-day itinerary with Amap map, budget visualizer, preferences screen, auth, responsive.
- Deployment recipe (docker-compose dev; container platform prod).

**Explicit V3 non-goals.** Mobile native apps. Payment/booking. Social/sharing beyond a "copy link".

---

## 5. Which components should remain tools

Rule of thumb: **tools = deterministic, narrow, idempotent-ish; no LLM reasoning inside.** Everything we already have in V0 stays as a tool, with V1 swapping the implementation behind some of them.

Keep as tools (V1 → V3):
- `record_trip_request` — pure state writer via `Command`.
- `save_preference` — pure store writer + `Command`/`ToolMessage`.
- `find_attractions` (V1: Amap POI search).
- `get_weather` (V1: Amap weather).
- `route_between` (V1, new) — single API call.
- `search_flights`, `search_hotels` — stay mock through V1; possibly real in V2/V3.
- `estimate_budget` — pure arithmetic; remains a tool.
- Geocoding helper (internal, not necessarily LLM-exposed).
- Any future single-API-call utility (currency conversion, public-holiday lookup, district info).

---

## 6. Which components should become specialized agents

Rule of thumb: **agent = needs reasoning, multi-step, judgment, or branching across many tools.**

Become agents in V2:
- Intake / clarification (multi-turn judgment about which questions to ask, when to stop).
- Destination research (compose POI searches, summarize, filter by interests/weather/season).
- Logistics planning (sequence POIs across days, minimize travel time, respect opening hours).
- Budget optimization (iterate trade-offs across comfort levels and POI selection).
- Itinerary composition (the final structured `TripPlan` writer).
- Critic / QA (cross-check plan against constraints; trigger revision).
- Preference management (extract learnings post-trip; recommend based on history).

---

## 7. Proposed V2 multi-agent roles

| Agent | Owns | Inputs | Outputs (state writes) | Tools it uses |
|---|---|---|---|---|
| **Supervisor / Router** | next-node decision | full state | routing decision | (no tools; pure conditional edges) |
| **Intake** | parse user → `TripRequest`; bounded clarification | last user messages, prior `trip_request` | `trip_request`, `clarification_rounds` | `record_trip_request` |
| **Preference Manager (pre)** | inject known prefs | `user_id` | `user_preferences` in state | `JsonPreferenceStore.load_user_preferences` |
| **Destination Researcher** | candidate POIs + context | `trip_request`, `user_preferences` | `candidates: list[Activity]`, `local_context` | `find_attractions`, `get_weather`, geocoding |
| **Logistics Planner** | per-day sequencing + transit | `candidates`, `trip_request` | `day_skeleton: list[DayPlan]` (no prices yet) | `route_between`, `get_weather` |
| **Budget Optimizer** | costing + comfort-tier alternatives | `day_skeleton`, `comfort_level`, `party_size` | `budget`, `flight_options`, `hotel_options`, possibly `revised_skeleton` | `estimate_budget`, `search_flights`/`search_hotels` |
| **Itinerary Composer** | final `TripPlan` (structured output) | everything above | `structured_response: TripPlan` | (none; uses `response_format`) |
| **Critic / QA** | constraint check + revision request | `TripPlan` draft + `trip_request` | `revision_request` or approval | (read-only) |
| **Preference Manager (post)** | extract durable prefs | final `TripPlan` + transcript | persisted `UserPreferences` updates | `save_preference` |

Each agent is itself a small `create_agent` (or a 1–2 node sub-graph) — i.e., V2 *uses* V0's primitives, doesn't throw them out.

---

## 8. Proposed V2 LangGraph `StateGraph` flow

```
                    ┌──────────────────┐
                    │      START       │
                    └─────────┬────────┘
                              ▼
                    ┌──────────────────┐
                    │ preferences_pre  │  load UserPreferences → state.context
                    └─────────┬────────┘
                              ▼
                    ┌──────────────────┐
                    │      intake      │  parse + decide_clarification (bounded)
                    └─────────┬────────┘
                              │
              ┌───────────────┴───────────────┐
              │ trip_request incomplete?       │
              ▼ yes (interrupt)                ▼ no
       ┌────────────┐                  ┌────────────────┐
       │  clarify   │  (human-in-loop) │   supervisor   │
       │  (asks)    │                  └────────┬───────┘
       └─────┬──────┘                           │ fan-out (parallel)
             │ resume                            │
             └────────────► intake               ▼
                                  ┌───────────────────────────────┐
                                  │  research  │ logistics │ budget │  (concurrent branches)
                                  └────┬───────┴─────┬─────┴───┬───┘
                                       │ join (fan-in)         │
                                       ▼                       │
                              ┌────────────────────┐           │
                              │ itinerary_composer │ ◄─────────┘
                              └─────────┬──────────┘
                                        ▼
                              ┌────────────────────┐
                              │      critic        │
                              └─────────┬──────────┘
                                        │ revision?
                              yes ──────┴────── no
                               │                │
                               ▼                ▼
                          (route back to    ┌──────────────────┐
                           the relevant     │ preferences_post │  extract + save prefs
                           branch with      └─────────┬────────┘
                           revision_request)          ▼
                                                  ┌─────┐
                                                  │ END │  emits TripPlan
                                                  └─────┘
```

**Edges:**
- Conditional from `intake` to `clarify` (interrupt) vs `supervisor`.
- `supervisor` fans out to `{research, logistics, budget}` (three concurrent edges).
- Implicit join before `itinerary_composer` (LangGraph awaits all incoming edges).
- Conditional from `critic` back to `supervisor` (with a `revision_request` field in state) or forward to `preferences_post`.
- Revision-loop budget enforced by a `revision_count` state key + a hard cap (mirrors the M7 bounded-clarification idea).

**Reused V0 mechanisms:** `Command(update=...)` everywhere; `TripPlan` `response_format` only on `itinerary_composer`; checkpointer + `thread_id` (now Postgres in V3); long-term memory through preferences manager nodes.

---

## 9. Amap API integration scope (V1)

**In scope (V1).**

| Amap endpoint | Used for | Replaces / introduces |
|---|---|---|
| `/geocode/geo` + `/geocode/regeo` | city/place ↔ coords + adcode | internal geocoding helper |
| `/place/text` + `/place/around` | POI by keyword + radius + category | replaces mock `find_attractions` |
| `/config/district` | admin region lookup | internal (city → adcode) |
| `/direction/{driving,walking,transit/integrated,bicycling}` | route time/distance | new `route_between` tool |
| `/weather/weatherInfo` | live + 3-day forecast by adcode | replaces mock `get_weather` |

**Out of scope (V1).**
- Real-time traffic, indoor maps, ride-hailing, business-status, ratings depth.
- Amap **JSAPI / Web SDK** — that's V3 frontend; V1 is server-side Web Service API only.
- Flights/hotels via Amap (not its strength).

**Engineering shape.**
- New module `travel_assistant/providers/amap/` with a typed `httpx` client (sync first; async if streaming benefits emerge).
- `Settings` adds `AMAP_API_KEY`, `AMAP_BASE_URL` (default), `PROVIDER_POI/WEATHER/ROUTE` (`mock` default, `amap` opt-in).
- Cache layer (per-process LRU + optional disk cache via existing data dir) keyed by request fingerprint.
- Retry/backoff via `tenacity` (already pinned in V0) on transient errors only; respect Amap rate limits (per-second + daily quota).
- **Coordinate caveat:** Amap uses **GCJ-02**; document this and pin all coordinates to GCJ-02 internally in V1 (V3 may need WGS84/GCJ-02 conversion for cross-provider integration).
- Logging: structured, **never log the API key**.
- Tests: cassette-based; CI default path stays offline using mocks; a marked `integration` suite hits Amap when `AMAP_API_KEY` is set.

**Risks specific to Amap.** Chinese-IP reachability/latency for non-CN reviewers (mitigate with caching + graceful mock fallback); account identity verification (interviewer can run mock path without ever getting a key); quota changes; English-language POIs sometimes weaker than Chinese (start with Chinese-name flows, then bilingual).

---

## 10. Web backend requirements (V3)

**Stack.** FastAPI + Uvicorn; consider `langserve` for graph endpoints; Pydantic v2 (already in V0); SQLAlchemy 2 + Alembic; Postgres; Redis (rate-limit + ephemeral cache); pytest + `httpx` async client.

**Endpoints (initial cut).**
- `POST /v1/sessions` → `{thread_id}`; `GET /v1/sessions/{tid}` → history.
- `POST /v1/sessions/{tid}/messages` (SSE) — streams agent events (mirrors V0 `Runner.stream`).
- `POST /v1/sessions/{tid}/cancel`.
- `GET/PUT /v1/users/{user_id}/preferences`.
- `GET/POST /v1/plans/{plan_id}`; `POST /v1/sessions/{tid}/save-plan`.
- `POST /v1/auth/login`, `POST /v1/auth/refresh` (JWT or session).
- `GET /healthz`, `/readyz`, `/metrics` (Prometheus).

**Persistence.**
- `users`, `sessions(thread_id)`, `plans(snapshot of TripPlan)`, `messages` (thin transcript for audit).
- **Short-term memory:** LangGraph Postgres checkpointer (replaces V0's sqlite saver and retires the `_MetadataSerde` shim once CL-1 lands or by direct Postgres-saver adoption — V3 may make CL-1 moot if we leave sqlite behind).
- **Long-term memory:** LangGraph `BaseStore` over Postgres for preferences (closes the M3 `UPGRADE.md` path; `PreferenceStore` Protocol stays, just a new impl).

**Cross-cutting.**
- Settings extends V0's `Settings` (same pydantic-settings file).
- Streaming via SSE (simpler, replay-friendly, proxy-friendly); WebSocket only if SSE proves insufficient.
- Auth: token-based first (JWT); OAuth (GitHub/Google) v3.x.
- CORS configured for the SPA origin.
- Rate limiting per `user_id` (Redis token bucket).
- Observability: structured JSON logs; OpenTelemetry; LangSmith optional via env (already wired in V0).
- Security: prompt-injection-aware tool surface (no shell/file tools); user-input length caps; secret manager for keys in prod.
- Deploy: Docker; `docker-compose.yml` for dev (api + postgres + redis); production on a container platform (Fly.io / Render / Cloud Run).

---

## 11. Web frontend requirements (V3)

**Stack.** React 19 + TypeScript + Vite; Tailwind CSS; React Query (server state) + Zustand (UI state); React Router; Vitest + Testing Library + Playwright (E2E).

**Key surfaces.**
- **Chat panel.** Streamed assistant turns (SSE), step lines (agent node names) + final structured `TripPlan` card. Input box with "send", "regenerate", "cancel".
- **Itinerary view.** Day-by-day list with drag-reorder activities; per-activity drawer (POI details, opening hours, photos from Amap when available).
- **Map view.** Amap **JSAPI** (web SDK) showing POIs as markers, day-routes as polylines, day-toggle to switch shown set; cluster markers when zoomed out.
- **Budget panel.** Visual breakdown (donut/bars); comfort-tier slider that triggers a re-plan turn.
- **Preferences page.** CRUD with autosave; "extracted from your last trip" preview.
- **Auth.** Login/logout; account page.
- **Responsive.** Mobile-first; offline-friendly read of cached plans.

**Quality bar.** ESLint + Prettier; component tests for the streaming chat; Playwright happy-path E2E; a11y (axe-core) baseline; Lighthouse perf budget.

**Out of scope V3.0.** Real-time multiplayer editing, share/collaborate, mobile native apps.

---

## 12. Milestone roadmap (high-level)

> Each "Mx" below is a future milestone in its own right; not yet a spec/plan. CL-1 sits between V0 and V1 unless deferred further.

| Phase | Milestones | Highlights | Exit criteria |
|---|---|---|---|
| **V0.x housekeeping** | CL-1 (optional pre-V1) | sqlite serde pin alignment; shim removal if pin pair proven | Sqlite path works with vanilla `SqliteSaver(conn)`; shim deleted or kept with note |
| **V1 — real APIs** | M10 Amap client + config | typed client, retries, rate limit, cache | Cassette test green; key never logged |
| | M11 `find_attractions` → Amap | replace mock; provider switch | Same `TripPlan` structure; mock fallback works |
| | M12 `get_weather` → Amap | weather forecast by adcode | Day-weather populated from Amap |
| | M13 `route_between` tool | logistics-aware future-proofing | Tool returns time/distance/mode |
| | M14 Provider abstraction + docs + V1 release | clean swap interface; README v1 | `make ci` green; published tag `v1.0` |
| **V2 — multi-agent** | M15 shared state + supervisor scaffold | `StateGraph` skeleton | Smoke test of routing |
| | M16 intake/clarification sub-graph | wire `decide_clarification` | One-field & multi-field cases pass |
| | M17 parallel research/logistics/budget | fan-out/fan-in | All three nodes write expected state |
| | M18 itinerary composer + critic loop | revision-budget enforced | Critic can request revision N≤K |
| | M19 prefs manager (pre/post extraction) | closes V0 spec §14 v2 item | New session reflects extracted prefs |
| **V3 — web** | M20 FastAPI scaffold + SSE | session/message endpoints | `curl`/HTTPie streams events |
| | M21 Postgres persistence + checkpointer/store | retire JSON + sqlite | Resume across processes; prefs via `BaseStore` |
| | M22 React shell + chat streaming | end-to-end happy path | Plan rendered in browser |
| | M23 Amap web SDK + map view | POIs/routes on map | Day toggles render correctly |
| | M24 Itinerary editor + prefs + auth | drag-reorder, login | E2E happy path passes |
| | M25 Deploy + observability + V3 release | docker + traces + metrics | Public demo URL live |

---

## 13. Risks and tradeoffs

**Product / API.**
- *Amap regional reachability / quotas:* mitigate with caching + mock fallback + clear setup docs.
- *Coordinate systems (GCJ-02 vs WGS84):* enforce GCJ-02 internally in V1; revisit if mixing providers later.
- *Flights/hotels real data is hard:* keep mock through V1; consider only well-defined providers (e.g. Amadeus) in V2 with a stretch goal.

**Architecture.**
- *Multi-agent latency & token cost:* parallelize where independent, cap revision rounds, cache provider responses, allow comfort/precision settings to throttle.
- *State schema reshape from V1 to V2 will be breaking* (additive fields + new keys): plan a one-shot migration; do not try to keep V1 graph alive in parallel.
- *Hand-rolled `StateGraph` is more code to maintain than `create_agent`:* counterweight is the LangGraph showcase value V2 explicitly aims for.

**Engineering.**
- *Fake-model harness scales poorly across many scripted turns:* invest in a higher-level "test scenario" abstraction in V2 (event-driven assertions over message-order assertions).
- *Sqlite serde shim (CL-1):* still works; V3 may sidestep entirely by adopting Postgres saver. Decision point: do CL-1 now (cleaner V1) or skip and let V3's Postgres move retire it.
- *DeepSeek structured-output strategy is still UNVERIFIED:* a live call against DeepSeek with `response_format=TripPlan` should be added to V1 as a one-time integration test gated by `DEEPSEEK_API_KEY`, to close the spike's open finding before V2 doubles the structured-output surface.

**Productization (V3).**
- *Prompt injection via user input:* keep the tool surface narrow (no file/shell); validate inputs; consider per-user rate caps.
- *Privacy:* explicit consent on preference learning; deletion endpoint; minimize PII.
- *Cost runaway:* per-user / per-thread token caps; LangSmith for diagnosis but optional in prod.

---

## 14. What should not be done yet

- **No code, no dependency changes, no CL-1 work** (per the user instruction at the time of writing).
- **No hand-rolled `StateGraph` in V1.** V1 stays on `create_agent`; the only V1 architectural change is *provider* swapping behind tools.
- **No real flight/hotel providers in V1.** Defer to V1.5 / V2; do not add `amadeus`, `ctrip`, etc. to dependencies.
- **No web backend or frontend code until V2 is stable.** Avoid building UI on a graph that's about to be reshaped.
- **No replacement of `create_agent` with a different framework** (e.g., LangGraph-only, AutoGen, CrewAI). Stay on the LangChain 1.x line.
- **No automatic post-model preference extraction in V1.** Stays in V2 with the multi-agent prefs manager (it's coupled to the critic/composer flow).
- **No LangGraph `BaseStore` migration in V1.** Long-term memory stays JSON until V3 brings Postgres.
- **No LangSmith default-on.** Stays env-gated through V1 and dev-only in V2; production posture decided at V3.
- **No baking of `AMAP_API_KEY` or `DEEPSEEK_API_KEY` anywhere in the repo / examples / fixtures.**
- **No premature multi-agent abstractions in V1.** Don't introduce a "supervisor" concept just because V2 will need one; keep V1's surface small.
- **No deletion of the V0 mock tools.** They remain the default + the offline harness (mock provider stays selectable forever).
- **No CI weakening** to accommodate live calls. Integration tests are marked + opt-in via env.

---

## Suggested next step (when ready)

If this direction is acceptable, the natural next step (still no code) is to pick the next milestone block (most likely **V1 / Amap**) and run the brainstorming → spec → plan sequence again for it — same shape as V0 (small, reviewable steps; explicit gates), producing `docs/superpowers/specs/<date>-v1-amap-integration.md` and a matching plan. The CL-1 vs ship-V1-first decision is the only ordering choice that meaningfully affects the immediate next milestone.
