"""AmapRouteProvider — RouteResult with `provider` provenance + fallback."""
from __future__ import annotations

import logging

from travel_assistant.models import RouteResult
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.route import RouteProvider

_LOG = logging.getLogger("travel_assistant.providers.amap.route")

_MODE_ENDPOINT: dict[str, str] = {
    "driving": "direction/driving",
    "walking": "direction/walking",
    "transit": "direction/transit/integrated",
    "bicycling": "direction/bicycling",
}


class AmapRouteProvider:
    def __init__(
        self,
        client: AmapHttpClient,
        geocoding: GeocodingProvider,
        fallback: RouteProvider,
    ) -> None:
        self._client = client
        self._geo = geocoding
        self._fallback = fallback

    def route_between(
        self, origin: str, destination: str, mode: str = "driving"
    ) -> RouteResult:
        if mode not in _MODE_ENDPOINT:
            return self._mock_with_reason(
                origin, destination, mode, f"unsupported mode {mode!r}"
            )
        o_geo = self._geo.geocode(origin)
        d_geo = self._geo.geocode(destination)
        if (
            o_geo is None
            or d_geo is None
            or o_geo.country != "中国"
            or d_geo.country != "中国"
            or o_geo.longitude is None
            or o_geo.latitude is None
            or d_geo.longitude is None
            or d_geo.latitude is None
        ):
            return self._mock_with_reason(
                origin, destination, mode, "non-CN or unresolvable endpoint(s)"
            )
        try:
            data = self._client.get(
                _MODE_ENDPOINT[mode],
                {
                    "origin": f"{o_geo.longitude},{o_geo.latitude}",
                    "destination": f"{d_geo.longitude},{d_geo.latitude}",
                },
            )
        except AmapError as e:
            return self._mock_with_reason(
                origin, destination, mode, f"upstream error: {type(e).__name__}"
            )

        route = data.get("route") or {}
        paths = route.get("paths") or []
        if not paths:
            return self._mock_with_reason(
                origin, destination, mode, "empty paths"
            )
        first = paths[0]
        try:
            distance_m = int(first.get("distance"))
            duration_s = int(first.get("duration"))
        except (TypeError, ValueError):
            return self._mock_with_reason(
                origin, destination, mode, "malformed paths"
            )
        return RouteResult(
            origin=origin,
            destination=destination,
            mode=mode,
            distance_m=distance_m,
            duration_s=duration_s,
            provider="amap",
        )

    def _mock_with_reason(
        self, origin: str, destination: str, mode: str, reason: str
    ) -> RouteResult:
        _LOG.info(
            "[amap] route %s->%s mode=%s falling back to mock: %s",
            origin, destination, mode, reason,
        )
        m = self._fallback.route_between(origin, destination, mode)
        return RouteResult(
            origin=m.origin,
            destination=m.destination,
            mode=m.mode,
            distance_m=m.distance_m,
            duration_s=m.duration_s,
            provider="mock-fallback",
            fallback_reason=reason,
        )
