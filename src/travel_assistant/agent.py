"""create_agent assembly.

response_format is the RAW TripPlan schema: create_agent's AutoStrategy then
picks ProviderStrategy for profiled models (real DeepSeek) and the ToolStrategy
fallback for profile-less ones (the test fake). This raw-schema form is what
makes both paths work without hardcoding a strategy (DeepSeek's real strategy
is still UNVERIFIED — see docs/superpowers/notes/api-spike-findings.md).
"""
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from travel_assistant.models import TripPlan
from travel_assistant.prompts import SYSTEM_PROMPT
from travel_assistant.state import TravelAgentState


def build_agent(
    model: BaseChatModel,
    tools: list[Any],
    checkpointer: Any,
    preferences_block: str,
) -> CompiledStateGraph:
    """Assemble the travel agent: model + wired tools + TripPlan response_format + checkpointer."""
    system_prompt = f"{SYSTEM_PROMPT}\n\n{preferences_block}"
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        response_format=TripPlan,
        state_schema=TravelAgentState,
        checkpointer=checkpointer,
    )
