"""WeatherProvider Protocol. Implementations: providers.mock.weather, providers.amap.weather."""
from typing import Protocol


class WeatherProvider(Protocol):
    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        ...


def get_weather_provider(settings):  # type: ignore[no-untyped-def]
    """Return the WeatherProvider selected by settings. Mock is the default."""
    settings.validated()
    from travel_assistant.providers.mock.weather import MockWeatherProvider

    mock = MockWeatherProvider()
    if settings.travel_agent_provider_weather == "amap":
        from travel_assistant.providers.amap._client import AmapHttpClient
        from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
        from travel_assistant.providers.amap.weather import AmapWeatherProvider

        client = AmapHttpClient(settings)
        return AmapWeatherProvider(client, AmapGeocodingProvider(client), mock)
    return mock
