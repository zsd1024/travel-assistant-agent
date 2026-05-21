import pytest

from travel_assistant.config import Settings
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.poi import AmapPOIProvider
from travel_assistant.providers.amap.route import AmapRouteProvider
from travel_assistant.providers.amap.weather import AmapWeatherProvider
from travel_assistant.providers.geocoding import get_geocoding_provider
from travel_assistant.providers.mock.geocoding import MockGeocodingProvider
from travel_assistant.providers.mock.poi import MockPOIProvider
from travel_assistant.providers.mock.route import MockRouteProvider
from travel_assistant.providers.mock.weather import MockWeatherProvider
from travel_assistant.providers.poi import get_poi_provider
from travel_assistant.providers.route import get_route_provider
from travel_assistant.providers.weather import get_weather_provider


def test_default_factories_return_mock_providers() -> None:
    s = Settings()
    assert isinstance(get_poi_provider(s), MockPOIProvider)
    assert isinstance(get_weather_provider(s), MockWeatherProvider)
    assert isinstance(get_route_provider(s), MockRouteProvider)
    assert isinstance(get_geocoding_provider(s), MockGeocodingProvider)


def test_amap_factories_return_amap_providers_when_configured() -> None:
    s = Settings(
        travel_agent_provider_poi="amap",
        travel_agent_provider_weather="amap",
        travel_agent_provider_route="amap",
        travel_agent_provider_geocoding="amap",
        amap_api_key="K",
    )
    assert isinstance(get_poi_provider(s), AmapPOIProvider)
    assert isinstance(get_weather_provider(s), AmapWeatherProvider)
    assert isinstance(get_route_provider(s), AmapRouteProvider)
    assert isinstance(get_geocoding_provider(s), AmapGeocodingProvider)


def test_factory_rejects_amap_without_key() -> None:
    with pytest.raises(ValueError, match="AMAP_API_KEY"):
        get_poi_provider(Settings(travel_agent_provider_poi="amap"))


def test_factory_rejects_unknown_provider_value() -> None:
    with pytest.raises(ValueError, match="TRAVEL_AGENT_PROVIDER_ROUTE"):
        get_route_provider(Settings(travel_agent_provider_route="redis"))
