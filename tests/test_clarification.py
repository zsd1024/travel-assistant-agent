from travel_assistant.clarification import (
    MAX_CLARIFICATION_ROUNDS,
    decide_clarification,
)
from travel_assistant.models import ComfortLevel, TripRequest


def test_complete_request_no_clarification() -> None:
    tr = TripRequest(origin="Shanghai", destination="Tokyo", duration_days=5,
                      comfort_level=ComfortLevel.COMFORT)
    d = decide_clarification(tr, round_index=0)
    assert d.should_ask is False
    assert d.proceed_with_defaults is False
    assert d.questions == []


def test_only_budget_missing_one_focused_question() -> None:
    tr = TripRequest(origin="Shanghai", destination="Tokyo", duration_days=5)
    d = decide_clarification(tr, round_index=0)
    assert d.should_ask is True
    assert len(d.questions) == 1
    assert "comfort" in d.questions[0].lower() or "budget" in d.questions[0].lower()


def test_multiple_missing_bounded() -> None:
    tr = TripRequest(origin="Shanghai")  # destination, dates, comfort missing
    d = decide_clarification(tr, round_index=0)
    assert d.should_ask is True
    assert 1 < len(d.questions) <= 3


def test_all_missing_capped_at_three() -> None:
    tr = TripRequest()  # 4 critical missing
    d = decide_clarification(tr, round_index=0)
    assert len(d.questions) == 3


def test_round_bound_prevents_infinite_loop() -> None:
    tr = TripRequest(origin="Shanghai")
    d = decide_clarification(tr, round_index=MAX_CLARIFICATION_ROUNDS)
    assert d.should_ask is False
    assert d.proceed_with_defaults is True
