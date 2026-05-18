"""Deterministic mock flight search (no network)."""
import random

from travel_assistant.models import FlightOption

_CARRIERS = ("AirMock", "MockJet", "PseudoAir")


def search_flights(origin: str, destination: str, *, seed: int = 0) -> list[FlightOption]:
    """Return deterministic mock flights for a route.

    Graceful edge handling: blank origin/destination -> [] (unknown route).
    Same (origin, destination, seed) always yields identical results.
    """
    if not origin.strip() or not destination.strip():
        return []
    o, d = origin.strip(), destination.strip()
    rng = random.Random(f"flights:{o.lower()}->{d.lower()}:{seed}")
    return [
        FlightOption(
            carrier=c,
            depart=f"{o} 08:00",
            arrive=f"{d} 12:30",
            price=round(rng.uniform(220.0, 780.0), 2),
        )
        for c in _CARRIERS
    ]
