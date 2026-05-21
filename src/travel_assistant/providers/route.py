"""RouteProvider Protocol. Implementations: providers.mock.route, providers.amap.route."""
from typing import Protocol

from travel_assistant.models import RouteResult


class RouteProvider(Protocol):
    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        ...


def get_route_provider(settings):  # type: ignore[no-untyped-def]
    """Return the RouteProvider selected by settings. Mock is the default."""
    settings.validated()
    from travel_assistant.providers.mock.route import MockRouteProvider

    mock = MockRouteProvider()
    if settings.travel_agent_provider_route == "amap":
        from travel_assistant.providers.amap._client import AmapHttpClient
        from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
        from travel_assistant.providers.amap.route import AmapRouteProvider

        client = AmapHttpClient(settings)
        return AmapRouteProvider(client, AmapGeocodingProvider(client), mock)
    return mock
