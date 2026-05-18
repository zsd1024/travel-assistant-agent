"""Deterministic mock budget estimator (pure arithmetic, no randomness)."""
from travel_assistant.models import BudgetBreakdown, FlightOption, HotelOption


def estimate_budget(
    flights: list[FlightOption],
    hotels: list[HotelOption],
    nights: int,
    party_size: int,
    *,
    food_per_day: float = 45.0,
    activities_per_day: float = 35.0,
) -> BudgetBreakdown:
    """Estimate a trip budget from gathered options.

    Graceful edge handling: empty flights/hotels -> 0 for that component;
    non-positive nights/party_size clamped to 1. Deterministic (pure).
    """
    n = max(nights, 1)
    pax = max(party_size, 1)
    cheapest_flight = min((f.price for f in flights), default=0.0)
    cheapest_hotel = min((h.price_per_night for h in hotels), default=0.0)
    flights_total = round(cheapest_flight * pax, 2)
    lodging = round(cheapest_hotel * n, 2)
    food = round(food_per_day * n * pax, 2)
    activities = round(activities_per_day * n, 2)
    local = round(12.0 * n, 2)
    total = round(flights_total + lodging + food + activities + local, 2)
    return BudgetBreakdown(
        currency="USD",
        flights=flights_total,
        lodging=lodging,
        food=food,
        activities=activities,
        local_transport=local,
        total=total,
    )
