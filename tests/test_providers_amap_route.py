import httpx
import respx

from travel_assistant.config import Settings
from travel_assistant.models import RouteResult
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.route import AmapRouteProvider
from travel_assistant.providers.mock.route import MockRouteProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "北京市", "adcode": "110000",
                  "location": "116.481028,39.989643"}],
}
_TJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "天津市", "adcode": "120000",
                  "location": "117.190182,39.125596"}],
}
_DRIVING = {
    "status": "1", "info": "OK", "count": "1",
    "route": {
        "origin": "116.481028,39.989643", "destination": "117.190182,39.125596",
        "paths": [{"distance": "137995", "duration": "9233", "steps": []}],
    },
}


@respx.mock
def test_cn_route_returns_amap_provider() -> None:
    geo = respx.get("https://restapi.amap.com/v3/geocode/geo")
    geo.mock(side_effect=[
        httpx.Response(200, json=_BJ_GEO),
        httpx.Response(200, json=_TJ_GEO),
    ])
    respx.get("https://restapi.amap.com/v3/direction/driving").mock(
        return_value=httpx.Response(200, json=_DRIVING)
    )
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("北京", "天津", "driving")
    assert isinstance(r, RouteResult)
    assert r.provider == "amap"
    assert r.distance_m == 137995
    assert r.duration_s == 9233
    assert r.mode == "driving"


_EMPTY_GEO = {"status": "1", "info": "OK", "count": "0", "geocodes": []}


@respx.mock
def test_non_cn_origin_or_destination_falls_back() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_EMPTY_GEO)
    )
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("Paris", "Lyon", "driving")
    assert r.provider == "mock-fallback"
    assert "non-CN" in r.fallback_reason or "outside CN" in r.fallback_reason


@respx.mock
def test_upstream_error_falls_back_with_reason() -> None:
    geo = respx.get("https://restapi.amap.com/v3/geocode/geo")
    geo.mock(side_effect=[
        httpx.Response(200, json=_BJ_GEO),
        httpx.Response(200, json=_TJ_GEO),
    ])
    respx.get("https://restapi.amap.com/v3/direction/driving").mock(
        return_value=httpx.Response(503)
    )
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("北京", "天津", "driving")
    assert r.provider == "mock-fallback"
    assert "upstream" in r.fallback_reason.lower()


def test_unsupported_mode_falls_back_locally() -> None:
    # No HTTP calls expected.
    client = AmapHttpClient(_settings())
    p = AmapRouteProvider(client, AmapGeocodingProvider(client), MockRouteProvider())
    r = p.route_between("北京", "天津", "teleport")
    assert r.provider == "mock-fallback"
    assert "mode" in r.fallback_reason.lower()
