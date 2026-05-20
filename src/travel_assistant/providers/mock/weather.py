from travel_assistant.tools.weather import get_weather


class MockWeatherProvider:
    """Wraps tools.weather.get_weather."""

    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        return get_weather(city, days, seed=seed)
