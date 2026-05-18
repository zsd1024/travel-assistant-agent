from travel_assistant.tools.weather import get_weather


def test_weather_length_and_deterministic() -> None:
    assert get_weather("Tokyo", 5, seed=2) == get_weather("Tokyo", 5, seed=2)
    assert len(get_weather("Tokyo", 5, seed=2)) == 5


def test_weather_values_in_known_set() -> None:
    known = {"sunny", "partly cloudy", "light rain", "clear"}
    assert set(get_weather("Tokyo", 7, seed=3)) <= known


def test_weather_non_positive_days_empty() -> None:
    assert get_weather("Tokyo", 0) == []
    assert get_weather("Tokyo", -3) == []
