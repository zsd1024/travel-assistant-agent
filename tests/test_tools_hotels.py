from travel_assistant.models import ComfortLevel
from travel_assistant.tools.hotels import search_hotels


def test_hotels_tiered_and_deterministic() -> None:
    a = search_hotels("Tokyo", ComfortLevel.COMFORT, seed=1)
    b = search_hotels("Tokyo", ComfortLevel.COMFORT, seed=1)
    assert [h.model_dump() for h in a] == [h.model_dump() for h in b]
    assert all(90.0 <= h.price_per_night <= 200.0 for h in a)
    assert all(3.5 <= h.rating <= 5.0 for h in a)


def test_hotels_tiers_differ() -> None:
    budget = search_hotels("Tokyo", ComfortLevel.BUDGET, seed=1)
    luxury = search_hotels("Tokyo", ComfortLevel.LUXURY, seed=1)
    assert max(h.price_per_night for h in budget) <= 90.0
    assert min(h.price_per_night for h in luxury) >= 200.0


def test_hotels_blank_city_returns_empty() -> None:
    assert search_hotels("  ", ComfortLevel.COMFORT) == []
