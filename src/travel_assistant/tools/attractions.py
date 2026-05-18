"""Deterministic mock attraction finder (no network)."""
import random

from travel_assistant.models import Activity

_BY_INTEREST = {
    "food": (("Street food market", "food"), ("Sushi tasting", "food")),
    "city walks": (("Old town walk", "city walk"), ("Riverside stroll", "city walk")),
    "history": (("Castle tour", "history"), ("Museum visit", "history")),
}
_DEFAULT = (("City highlights tour", "sightseeing"),)


def find_attractions(
    city: str, interests: list[str], *, seed: int = 0
) -> list[Activity]:
    """Return deterministic mock attractions matching interests.

    Graceful edge handling: blank city -> uses "the city"; empty/blank or
    unknown interests fall back to a general sightseeing activity. Result is
    always non-empty. Same args+seed -> identical ordering.
    """
    safe_city = city.strip() or "the city"
    effective = [i for i in interests if i.strip()] or ["sightseeing"]
    rng = random.Random(
        f"attractions:{safe_city.lower()}:{','.join(sorted(effective))}:{seed}"
    )
    picked: list[Activity] = []
    for interest in effective:
        for name, cat in _BY_INTEREST.get(interest.lower(), _DEFAULT):
            picked.append(Activity(name=f"{name} ({safe_city})", category=cat))
    rng.shuffle(picked)
    return picked
