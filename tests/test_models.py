from datetime import date

from travel_assistant.models import (
    Activity,
    BudgetBreakdown,
    ComfortLevel,
    DayPlan,
    FlightOption,
    HotelOption,
    MissingField,
    TripPlan,
    TripRequest,
    UserPreferences,
)


def test_missing_critical_fields_only_comfort() -> None:
    req = TripRequest(origin="Shanghai", destination="Tokyo", duration_days=5)
    assert req.missing_critical_fields() == ["comfort_level"]
    assert req.is_ready_to_plan() is False


def test_missing_critical_fields_multiple_ordered() -> None:
    req = TripRequest(origin="Shanghai")
    assert req.missing_critical_fields() == [
        "destination",
        "dates_or_duration",
        "comfort_level",
    ]
    assert "origin" not in req.missing_critical_fields()


def test_dates_satisfy_via_start_end() -> None:
    req = TripRequest(
        origin="A",
        destination="B",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 5),
        comfort_level=ComfortLevel.BUDGET,
    )
    assert req.missing_critical_fields() == []
    assert req.is_ready_to_plan() is True


def test_complete_request_has_no_missing() -> None:
    req = TripRequest(
        origin="Shanghai",
        destination="Tokyo",
        duration_days=5,
        comfort_level=ComfortLevel.COMFORT,
        interests=["food"],
    )
    assert req.missing_critical_fields() == []
    assert req.is_ready_to_plan() is True
    assert req.clarification_targets() == []


def test_clarification_targets_single_focused() -> None:
    req = TripRequest(origin="Shanghai", destination="Tokyo", duration_days=5)
    targets = req.clarification_targets()
    assert len(targets) == 1
    assert isinstance(targets[0], MissingField)
    assert targets[0].field == "comfort_level"
    assert targets[0].label
    assert targets[0].example


def test_clarification_targets_multiple_match_missing() -> None:
    req = TripRequest(origin="Shanghai")
    targets = req.clarification_targets()
    assert [t.field for t in targets] == req.missing_critical_fields()


def test_party_size_and_interests_are_non_critical() -> None:
    req = TripRequest(
        origin="A", destination="B", duration_days=2, comfort_level=ComfortLevel.LUXURY
    )
    assert req.party_size == 1
    assert req.interests == []
    assert req.is_ready_to_plan() is True


def test_comfort_level_enum_values() -> None:
    assert ComfortLevel("budget") is ComfortLevel.BUDGET
    assert ComfortLevel.LUXURY.value == "luxury"


def test_activity_and_dayplan() -> None:
    act = Activity(name="Old town walk", category="city walk")
    day = DayPlan(day_index=1, date=date(2026, 6, 1), weather="sunny", activities=[act])
    assert day.activities[0].name == "Old town walk"
    assert day.activities[0].notes == ""


def test_flight_and_hotel_options_defaults() -> None:
    f = FlightOption(carrier="AirMock", depart="A 08:00", arrive="B 12:30", price=300.0)
    h = HotelOption(name="Central Hotel", area="Downtown", price_per_night=120.0)
    assert f.currency == "USD"
    assert h.currency == "USD" and h.rating == 0.0


def test_budget_breakdown_defaults() -> None:
    b = BudgetBreakdown()
    assert b.currency == "USD"
    assert b.total == 0.0


def test_tripplan_roundtrip() -> None:
    plan = TripPlan(
        summary="s",
        days=[
            DayPlan(
                day_index=1,
                date=date(2026, 6, 1),
                weather="sunny",
                activities=[Activity(name="walk", category="city walk")],
            )
        ],
        flight_options=[
            FlightOption(carrier="X", depart="A", arrive="B", price=250.0)
        ],
        hotel_options=[
            HotelOption(name="H", area="C", price_per_night=100.0)
        ],
        transport_notes="metro",
        budget=BudgetBreakdown(
            currency="USD",
            flights=0,
            lodging=0,
            food=0,
            activities=0,
            local_transport=0,
            total=0,
        ),
        assumptions=["party_size defaulted to 1"],
    )
    restored = TripPlan.model_validate_json(plan.model_dump_json())
    assert restored.summary == "s"
    assert restored.days[0].activities[0].category == "city walk"
    assert restored.flight_options[0].price == 250.0


def test_tripplan_minimal_defaults() -> None:
    plan = TripPlan(summary="only summary")
    assert plan.days == []
    assert plan.budget.total == 0.0
    assert plan.assumptions == []


def test_user_preferences() -> None:
    p = UserPreferences(user_id="u1", liked_interests=["food"],
                        preferred_comfort_level=ComfortLevel.COMFORT)
    assert p.user_id == "u1"
    assert p.home_city == ""
    assert UserPreferences(user_id="u2").liked_interests == []
