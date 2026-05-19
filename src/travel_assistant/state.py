"""Agent state schema: extends the real LangChain agent-state base with the
structured ``trip_request``, written by the ``record_trip_request`` tool via a
``Command`` state update.
"""
from __future__ import annotations

from langchain.agents import AgentState

from travel_assistant.models import TripRequest


class TravelAgentState(AgentState):
    trip_request: TripRequest | None
