from travel_assistant.models import RouteResult
from travel_assistant.tools.route import mock_route_between


class MockRouteProvider:
    """Wraps tools.route.mock_route_between."""

    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        return mock_route_between(origin, destination, mode)
