from travel_assistant.tools.attractions import find_attractions


def test_attractions_match_interests_deterministic() -> None:
    a = find_attractions("Tokyo", ["food"], seed=3)
    b = find_attractions("Tokyo", ["food"], seed=3)
    assert [x.model_dump() for x in a] == [x.model_dump() for x in b]
    assert any(x.category == "food" for x in a)


def test_attractions_empty_interests_fall_back() -> None:
    acts = find_attractions("Tokyo", [], seed=1)
    assert len(acts) >= 1
    assert acts[0].category == "sightseeing"


def test_attractions_unknown_interest_and_blank_city() -> None:
    acts = find_attractions("", ["underwater basket weaving"], seed=1)
    assert len(acts) >= 1
    assert "the city" in acts[0].name
