"""WeatherProvider Protocol. Implementations: providers.mock.weather, providers.amap.weather."""
from typing import Protocol


class WeatherProvider(Protocol):
    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        ...
