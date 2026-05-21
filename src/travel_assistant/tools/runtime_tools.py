"""M6: M2 tools + intake + save_preference wired with ToolRuntime / Command."""
from typing import Any

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from travel_assistant.config import Settings
from travel_assistant.memory.repository import PreferenceStore
from travel_assistant.models import ComfortLevel, TripRequest
from travel_assistant.providers.poi import get_poi_provider
from travel_assistant.providers.route import get_route_provider
from travel_assistant.providers.weather import get_weather_provider
from travel_assistant.tools import budget, flights, hotels
from travel_assistant.tools.intake import make_record_command
from travel_assistant.tools.preferences import persist_preference


def _call_id(runtime: ToolRuntime) -> str:
    """The tool-call id, always populated during tool execution.

    ``ToolRuntime.tool_call_id`` is typed ``str | None`` on the dataclass, but
    the tool-execution system always injects a concrete id when a tool runs
    (verified by the Task 2 spike). This narrows the type for callers that
    require ``str`` (e.g. ``make_record_command``)."""
    cid = runtime.tool_call_id
    if cid is None:  # pragma: no cover - defensive; never None during execution
        raise RuntimeError("tool_call_id missing during tool execution")
    return cid


def _trip_request(runtime: ToolRuntime) -> TripRequest:
    raw = runtime.state.get("trip_request")
    if raw is None:
        raise ValueError(
            "No trip request recorded yet; call record_trip_request first."
        )
    return raw if isinstance(raw, TripRequest) else TripRequest.model_validate(raw)


def build_tools(
    store: PreferenceStore, user_id: str, settings: Settings
) -> list[Any]:
    poi = get_poi_provider(settings)
    wx = get_weather_provider(settings)
    route_p = get_route_provider(settings)

    @tool
    def record_trip_request(
        runtime: ToolRuntime,
        origin: str,
        destination: str,
        duration_days: int | None = None,
        comfort_level: str | None = None,
        interests: list[str] | None = None,
        party_size: int = 1,
    ) -> Command:
        """Record the structured trip request once critical fields are known."""
        return make_record_command(
            _call_id(runtime),
            origin=origin,
            destination=destination,
            duration_days=duration_days,
            comfort_level=comfort_level,
            interests=interests,
            party_size=party_size,
        )

    @tool
    def search_flights_tool(runtime: ToolRuntime) -> list[dict[str, Any]]:
        """Search flights for the recorded trip."""
        tr = _trip_request(runtime)
        return [
            f.model_dump()
            for f in flights.search_flights(tr.origin or "", tr.destination or "")
        ]

    @tool
    def search_hotels_tool(runtime: ToolRuntime) -> list[dict[str, Any]]:
        """Search hotels for the recorded trip."""
        tr = _trip_request(runtime)
        return [
            h.model_dump()
            for h in hotels.search_hotels(
                tr.destination or "", tr.comfort_level or ComfortLevel.COMFORT
            )
        ]

    @tool
    def get_weather_tool(runtime: ToolRuntime) -> list[str]:
        """Get a weather outlook for the destination."""
        tr = _trip_request(runtime)
        return wx.forecast(tr.destination or "", tr.duration_days or 3)

    @tool
    def find_attractions_tool(runtime: ToolRuntime) -> list[dict[str, Any]]:
        """Find attractions matching the traveler's interests."""
        tr = _trip_request(runtime)
        return [
            a.model_dump()
            for a in poi.search(tr.destination or "", tr.interests)
        ]

    @tool
    def estimate_budget_tool(runtime: ToolRuntime) -> dict[str, Any]:
        """Estimate the trip budget from the recorded trip."""
        tr = _trip_request(runtime)
        fl = flights.search_flights(tr.origin or "", tr.destination or "")
        ho = hotels.search_hotels(
            tr.destination or "", tr.comfort_level or ComfortLevel.COMFORT
        )
        return budget.estimate_budget(
            fl, ho, tr.duration_days or 3, tr.party_size
        ).model_dump()

    @tool
    def route_between(
        runtime: ToolRuntime,
        origin: str,
        destination: str,
        mode: str = "driving",
    ) -> dict[str, Any]:
        """Compute time and distance between two places (Amap or mock)."""
        _ = runtime  # ToolRuntime injection point; not used here.
        return route_p.route_between(origin, destination, mode).model_dump()

    @tool
    def save_preference(
        runtime: ToolRuntime,
        liked_interests: list[str] | None = None,
        preferred_comfort_level: str | None = None,
        pace_notes: str = "",
        dietary_notes: str = "",
        home_city: str = "",
    ) -> Command:
        """Persist durable traveler preferences to the long-term store."""
        persist_preference(
            store,
            user_id,
            {
                "liked_interests": liked_interests,
                "preferred_comfort_level": preferred_comfort_level,
                "pace_notes": pace_notes,
                "dietary_notes": dietary_notes,
                "home_city": home_city,
            },
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"preferences saved for {user_id}",
                        tool_call_id=_call_id(runtime),
                    )
                ]
            }
        )

    return [
        record_trip_request,
        search_flights_tool,
        search_hotels_tool,
        get_weather_tool,
        find_attractions_tool,
        estimate_budget_tool,
        route_between,
        save_preference,
    ]
