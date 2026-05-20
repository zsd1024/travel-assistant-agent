"""RouteProvider Protocol. Implementations: providers.mock.route, providers.amap.route."""
from typing import Protocol

from travel_assistant.models import RouteResult


class RouteProvider(Protocol):
    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        ...
