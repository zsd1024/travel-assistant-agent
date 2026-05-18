from travel_assistant.tools.flights import search_flights


def test_flights_deterministic_and_typed() -> None:
    a = search_flights("Shanghai", "Tokyo", seed=42)
    b = search_flights("Shanghai", "Tokyo", seed=42)
    assert [f.model_dump() for f in a] == [f.model_dump() for f in b]
    assert len(a) >= 1 and a[0].price > 0
    assert a[0].currency == "USD"


def test_flights_different_seed_differs() -> None:
    a = search_flights("Shanghai", "Tokyo", seed=1)
    b = search_flights("Shanghai", "Tokyo", seed=2)
    assert [f.price for f in a] != [f.price for f in b]


def test_flights_blank_route_returns_empty() -> None:
    assert search_flights("", "Tokyo") == []
    assert search_flights("Shanghai", "   ") == []
