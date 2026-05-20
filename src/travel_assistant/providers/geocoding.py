"""GeocodingProvider Protocol. Implementations: providers.mock.geocoding, providers.amap.geocoding."""  # noqa: E501
from typing import Protocol

from travel_assistant.models import GeocodeResult


class GeocodingProvider(Protocol):
    def geocode(self, city: str) -> GeocodeResult | None:
        ...
