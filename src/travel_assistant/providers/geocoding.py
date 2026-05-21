"""GeocodingProvider Protocol. Implementations: providers.mock.geocoding, providers.amap.geocoding."""  # noqa: E501
from typing import Protocol

from travel_assistant.models import GeocodeResult


class GeocodingProvider(Protocol):
    def geocode(self, city: str) -> GeocodeResult | None:
        ...


def get_geocoding_provider(settings):  # type: ignore[no-untyped-def]
    """Return the GeocodingProvider selected by settings. Mock is the default."""
    settings.validated()
    from travel_assistant.providers.mock.geocoding import MockGeocodingProvider

    if settings.travel_agent_provider_geocoding == "amap":
        from travel_assistant.providers.amap._client import AmapHttpClient
        from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider

        return AmapGeocodingProvider(AmapHttpClient(settings))
    return MockGeocodingProvider()
