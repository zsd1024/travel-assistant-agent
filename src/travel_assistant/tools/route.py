"""Deterministic mock route helper (pure, used by MockRouteProvider)."""
import random

from travel_assistant.models import RouteResult

_VALID_MODES = ("driving", "walking", "transit", "bicycling")


def mock_route_between(
    origin: str, destination: str, mode: str = "driving", *, seed: int = 0
) -> RouteResult:
    """Return a deterministic mock RouteResult.

    Graceful edge handling: unknown mode falls back to ``"driving"``.
    Same args + seed -> identical output.
    """
    effective_mode = mode if mode in _VALID_MODES else "driving"
    o = origin.strip() or "unknown"
    d = destination.strip() or "unknown"
    rng = random.Random(f"route:{o.lower()}->{d.lower()}:{effective_mode}:{seed}")
    # Mode-specific bands (rough heuristics for a deterministic mock).
    bands = {
        "driving": (5_000, 50_000),
        "walking": (500, 8_000),
        "transit": (3_000, 40_000),
        "bicycling": (1_000, 20_000),
    }
    lo, hi = bands[effective_mode]
    distance_m = rng.randint(lo, hi)
    # average speed (m/s): driving 13, walking 1.3, transit 8, bicycling 4
    speed = {"driving": 13.0, "walking": 1.3, "transit": 8.0, "bicycling": 4.0}[
        effective_mode
    ]
    duration_s = int(distance_m / speed)
    return RouteResult(
        origin=o,
        destination=d,
        mode=effective_mode,
        distance_m=distance_m,
        duration_s=duration_s,
        provider="mock",
    )
