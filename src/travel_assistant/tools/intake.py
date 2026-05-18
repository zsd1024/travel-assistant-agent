"""record_trip_request: the Command-based state writer for TripRequest."""
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from travel_assistant.models import ComfortLevel, TripRequest


def make_record_command(
    tool_call_id: str,
    *,
    origin: str,
    destination: str,
    duration_days: int | None = None,
    comfort_level: str | None = None,
    interests: list[str] | None = None,
    party_size: int = 1,
) -> Command:
    """Build the Command that records a TripRequest into agent state and
    appends a confirming ToolMessage. Pure & unit-testable (no runtime)."""
    req = TripRequest(
        origin=origin,
        destination=destination,
        duration_days=duration_days,
        comfort_level=ComfortLevel(comfort_level) if comfort_level else None,
        interests=interests or [],
        party_size=party_size,
    )
    return Command(
        update={
            "trip_request": req,
            "messages": [
                ToolMessage(content="trip request recorded", tool_call_id=tool_call_id)
            ],
        }
    )
