"""Deterministic mock hotel search (no network)."""
import random

from travel_assistant.models import ComfortLevel, HotelOption

_TIER = {
    ComfortLevel.BUDGET: (40.0, 90.0),
    ComfortLevel.COMFORT: (90.0, 200.0),
    ComfortLevel.LUXURY: (200.0, 600.0),
}


def search_hotels(
    city: str, comfort: ComfortLevel, *, seed: int = 0
) -> list[HotelOption]:
    """Return deterministic mock hotels for a city at a comfort tier.

    Graceful edge handling: blank city -> []. Same args+seed -> identical.
    """
    if not city.strip():
        return []
    c = city.strip()
    lo, hi = _TIER[comfort]
    rng = random.Random(f"hotels:{c.lower()}:{comfort.value}:{seed}")
    return [
        HotelOption(
            name=f"{c} {tag} Hotel",
            area=area,
            price_per_night=round(rng.uniform(lo, hi), 2),
            rating=round(rng.uniform(3.5, 5.0), 1),
        )
        for tag, area in (("Central", "Downtown"), ("Park", "Riverside"))
    ]
