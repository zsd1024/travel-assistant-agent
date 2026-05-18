from travel_assistant.models import FlightOption, HotelOption
from travel_assistant.tools.budget import estimate_budget


def test_budget_totals_add_up() -> None:
    b = estimate_budget(
        [FlightOption(carrier="X", depart="a", arrive="b", price=300.0)],
        [HotelOption(name="H", area="C", price_per_night=100.0)],
        nights=4,
        party_size=2,
    )
    assert b.total == round(
        b.flights + b.lodging + b.food + b.activities + b.local_transport, 2
    )
    assert b.flights == 600.0
    assert b.lodging == 400.0


def test_budget_deterministic() -> None:
    args = (
        [FlightOption(carrier="X", depart="a", arrive="b", price=250.0)],
        [HotelOption(name="H", area="C", price_per_night=120.0)],
        3,
        1,
    )
    assert estimate_budget(*args).model_dump() == estimate_budget(*args).model_dump()


def test_budget_empty_lists_and_nonpositive_clamped() -> None:
    b = estimate_budget([], [], nights=0, party_size=0)
    assert b.flights == 0.0 and b.lodging == 0.0
    assert b.food == 45.0
    assert b.total == round(b.food + b.activities + b.local_transport, 2)
