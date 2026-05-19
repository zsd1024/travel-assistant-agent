"""Optional LangSmith tracing — env-gated, no hard-coded secrets.

Enabling is controlled solely by Settings (LANGSMITH_TRACING / LANGSMITH_API_KEY
env vars). LangChain/LangSmith auto-instrument when LANGSMITH_TRACING=true and a
key is present; this module only propagates that configuration cleanly before
the agent/runner is built. It never requires LangSmith for normal runs and never
embeds a key.
"""
import os

from travel_assistant.config import Settings


def configure_tracing(settings: Settings) -> bool:
    """Enable LangSmith tracing iff settings.langsmith_tracing. Returns whether
    it was enabled. Propagates a user-provided key only; hard-codes nothing."""
    if not settings.langsmith_tracing:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    return True
