from travel_assistant.models import (
    Activity,
    GeocodeResult,
    RouteResult,
)
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.mock.geocoding import MockGeocodingProvider
from travel_assistant.providers.mock.poi import MockPOIProvider
from travel_assistant.providers.mock.route import MockRouteProvider
from travel_assistant.providers.mock.weather import MockWeatherProvider
from travel_assistant.providers.poi import POIProvider
from travel_assistant.providers.route import RouteProvider
from travel_assistant.providers.weather import WeatherProvider


def test_mock_poi_protocol_and_determinism() -> None:
    p: POIProvider = MockPOIProvider()
    a = p.search("Tokyo", ["food"], seed=3)
    b = p.search("Tokyo", ["food"], seed=3)
    assert [x.model_dump() for x in a] == [x.model_dump() for x in b]
    assert any(isinstance(x, Activity) and x.category == "food" for x in a)


def test_mock_weather_protocol_and_determinism() -> None:
    p: WeatherProvider = MockWeatherProvider()
    assert p.forecast("Tokyo", 5, seed=2) == p.forecast("Tokyo", 5, seed=2)
    assert len(p.forecast("Tokyo", 5, seed=2)) == 5
    assert p.forecast("Tokyo", 0) == []


def test_mock_route_protocol_and_shape() -> None:
    p: RouteProvider = MockRouteProvider()
    r = p.route_between("Beijing", "Tianjin", "driving")
    assert isinstance(r, RouteResult)
    assert r.provider == "mock"
    assert r.distance_m > 0 and r.duration_s > 0
    assert r.mode == "driving"
    # determinism
    r2 = p.route_between("Beijing", "Tianjin", "driving")
    assert r2.model_dump() == r.model_dump()


def test_mock_route_invalid_mode_falls_back_to_driving() -> None:
    p = MockRouteProvider()
    r = p.route_between("A", "B", "unknown-mode")
    assert r.mode == "driving"


def test_mock_geocoding_cn_whitelist_and_unknown() -> None:
    p: GeocodingProvider = MockGeocodingProvider()
    g = p.geocode("北京")
    assert isinstance(g, GeocodeResult)
    assert g.country == "中国"
    assert g.adcode == "110000"
    assert p.geocode("Atlantis") is None  # unknown city -> None


def test_mock_geocoding_english_aliases() -> None:
    p = MockGeocodingProvider()
    assert p.geocode("Beijing") is not None
    assert p.geocode("beijing") is not None  # case-insensitive
    assert p.geocode("Shanghai") is not None
    assert p.geocode("Tokyo") is None  # not in CN whitelist
