import importlib

import pytest

from travel_assistant.config import Settings


def test_default_providers_are_mock_and_no_key_required() -> None:
    s = Settings().validated()
    assert s.travel_agent_provider_poi == "mock"
    assert s.travel_agent_provider_weather == "mock"
    assert s.travel_agent_provider_route == "mock"
    assert s.travel_agent_provider_geocoding == "mock"
    assert s.amap_api_key is None  # no key required for default mock path


def test_unknown_provider_value_rejected() -> None:
    with pytest.raises(ValueError, match="TRAVEL_AGENT_PROVIDER_POI"):
        Settings(travel_agent_provider_poi="redis").validated()


def test_amap_without_key_fails_fast() -> None:
    with pytest.raises(ValueError, match="AMAP_API_KEY"):
        Settings(
            travel_agent_provider_poi="amap", amap_api_key=None
        ).validated()


def test_amap_with_key_validates() -> None:
    s = Settings(
        travel_agent_provider_poi="amap",
        travel_agent_provider_weather="amap",
        amap_api_key="amap-test-key",
    ).validated()
    assert s.amap_api_key == "amap-test-key"


def test_protocols_import() -> None:
    # Protocols-only foundation: the 4 modules must import cleanly.
    for mod in (
        "travel_assistant.providers.poi",
        "travel_assistant.providers.weather",
        "travel_assistant.providers.route",
        "travel_assistant.providers.geocoding",
    ):
        importlib.import_module(mod)


def test_live_http_is_blocked_outside_respx() -> None:
    # The autouse conftest fixture must make an unintercepted httpx call raise.
    import httpx

    with pytest.raises(RuntimeError, match="Live HTTP request blocked"):
        httpx.get("https://example.invalid/")


def test_geocode_and_route_result_models() -> None:
    from travel_assistant.models import GeocodeResult, RouteResult

    g = GeocodeResult(city="北京", country="中国", province="北京市",
                      adcode="110000", longitude=116.4, latitude=39.9)
    assert g.country == "中国"
    assert g.adcode == "110000"

    r = RouteResult(origin="A", destination="B", mode="driving",
                    distance_m=7995, duration_s=1233, provider="amap")
    assert r.provider == "amap"
    assert r.fallback_reason == ""

    f = RouteResult(origin="A", destination="B", mode="walking",
                    distance_m=500, duration_s=400, provider="mock-fallback",
                    fallback_reason="non-CN destination")
    assert f.provider == "mock-fallback"
    assert "non-CN" in f.fallback_reason
