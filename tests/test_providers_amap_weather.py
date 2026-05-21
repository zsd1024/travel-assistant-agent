import logging

import httpx
import pytest
import respx

from travel_assistant.config import Settings
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.weather import AmapWeatherProvider
from travel_assistant.providers.mock.weather import MockWeatherProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "北京市", "adcode": "110000",
                  "location": "116.4,39.9"}],
}
_WX = {
    "status": "1", "info": "OK",
    "forecasts": [{
        "city": "北京市", "adcode": "110000",
        "casts": [
            {"date": "2026-06-01", "dayweather": "晴", "nightweather": "多云"},
            {"date": "2026-06-02", "dayweather": "多云", "nightweather": "晴"},
            {"date": "2026-06-03", "dayweather": "小雨", "nightweather": "阴"},
        ],
    }],
}


@respx.mock
def test_cn_city_uses_amap_forecast() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_GEO)
    )
    respx.get("https://restapi.amap.com/v3/weather/weatherInfo").mock(
        return_value=httpx.Response(200, json=_WX)
    )
    client = AmapHttpClient(_settings())
    p = AmapWeatherProvider(client, AmapGeocodingProvider(client), MockWeatherProvider())
    out = p.forecast("北京", 3)
    assert out == ["晴", "多云", "小雨"]


@respx.mock
def test_non_cn_city_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    _empty_geo = {"status": "1", "info": "OK", "count": "0", "geocodes": []}
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_empty_geo)
    )
    client = AmapHttpClient(_settings())
    p = AmapWeatherProvider(client, AmapGeocodingProvider(client), MockWeatherProvider())
    caplog.set_level(logging.INFO, logger="travel_assistant.providers.amap")
    out = p.forecast("Paris", 5)
    assert len(out) == 5  # mock honors `days`
    assert any("falling back to mock" in r.getMessage() for r in caplog.records)
