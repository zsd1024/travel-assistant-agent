"""Deterministic mock weather outlook (no network)."""
import random

_KINDS = ("sunny", "partly cloudy", "light rain", "clear")


def get_weather(city: str, days: int, *, seed: int = 0) -> list[str]:
    """Return a deterministic per-day weather outlook.

    Graceful edge handling: days <= 0 -> []. Same args+seed -> identical.
    """
    if days <= 0:
        return []
    rng = random.Random(f"weather:{city.strip().lower()}:{days}:{seed}")
    return [rng.choice(_KINDS) for _ in range(days)]
