"""POIProvider Protocol. Implementations: providers.mock.poi, providers.amap.poi."""
from typing import Protocol

from travel_assistant.models import Activity


class POIProvider(Protocol):
    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        ...


def get_poi_provider(settings):  # type: ignore[no-untyped-def]
    """Return the POIProvider selected by settings. Mock is the default."""
    settings.validated()
    from travel_assistant.providers.mock.poi import MockPOIProvider

    mock = MockPOIProvider()
    if settings.travel_agent_provider_poi == "amap":
        from travel_assistant.providers.amap._client import AmapHttpClient
        from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
        from travel_assistant.providers.amap.poi import AmapPOIProvider

        client = AmapHttpClient(settings)
        return AmapPOIProvider(client, AmapGeocodingProvider(client), mock)
    return mock
