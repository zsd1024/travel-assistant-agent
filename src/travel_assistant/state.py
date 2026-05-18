"""Agent state schema. Extends the real LangChain agent-state base.

The extra ``trip_request`` key is the M5 deliverable; nothing writes it yet
(the intake tool that sets it via ``Command`` arrives in M6).
"""
from __future__ import annotations

from langchain.agents import AgentState

from travel_assistant.models import TripRequest


class TravelAgentState(AgentState):
    trip_request: TripRequest | None
