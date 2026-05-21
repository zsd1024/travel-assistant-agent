import logging

import httpx
import pytest
import respx

from travel_assistant.config import Settings
from travel_assistant.models import Activity
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider
from travel_assistant.providers.amap.poi import AmapPOIProvider
from travel_assistant.providers.mock.poi import MockPOIProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_GEO = {
    "status": "1", "info": "OK", "count": "1",
    "geocodes": [{"country": "中国", "province": "北京市", "adcode": "110000",
                  "location": "116.4,39.9"}],
}
_POI_RESP = {
    "status": "1", "info": "OK", "count": "2",
    "pois": [
        {"id": "1", "name": "故宫博物院", "type": "风景名胜",
         "typecode": "110200", "address": "景山前街4号", "location": "116.4,39.9"},
        {"id": "2", "name": "南锣鼓巷", "type": "风景名胜",
         "typecode": "110200", "address": "鼓楼地区", "location": "116.4,39.9"},
    ],
}


@respx.mock
def test_cn_city_uses_amap_path() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_GEO)
    )
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(200, json=_POI_RESP)
    )
    client = AmapHttpClient(_settings())
    p = AmapPOIProvider(
        client=client,
        geocoding=AmapGeocodingProvider(client),
        fallback=MockPOIProvider(),
    )
    result = p.search("北京", ["city walks"])
    assert all(isinstance(a, Activity) for a in result)
    assert any("故宫" in a.name for a in result)


@respx.mock
def test_non_cn_city_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    _empty_geo = {"status": "1", "info": "OK", "count": "0", "geocodes": []}
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_empty_geo)
    )
    # No expectation on /place/text — must NOT be called for non-CN.
    client = AmapHttpClient(_settings())
    p = AmapPOIProvider(
        client=client,
        geocoding=AmapGeocodingProvider(client),
        fallback=MockPOIProvider(),
    )
    caplog.set_level(logging.INFO, logger="travel_assistant.providers.amap")
    result = p.search("Tokyo", ["food"])
    assert len(result) >= 1                                # mock always returns something
    assert any("falling back to mock" in r.getMessage() for r in caplog.records)


@respx.mock
def test_amap_upstream_error_falls_back_to_mock(caplog: pytest.LogCaptureFixture) -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_GEO)
    )
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(503)
    )
    client = AmapHttpClient(_settings())
    p = AmapPOIProvider(
        client=client,
        geocoding=AmapGeocodingProvider(client),
        fallback=MockPOIProvider(),
    )
    caplog.set_level(logging.INFO, logger="travel_assistant.providers.amap")
    result = p.search("北京", ["food"])
    assert len(result) >= 1
    assert any("falling back to mock" in r.getMessage() for r in caplog.records)
