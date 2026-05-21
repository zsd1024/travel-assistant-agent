import httpx
import respx

from travel_assistant.config import Settings
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap.geocoding import AmapGeocodingProvider


def _settings() -> Settings:
    return Settings(amap_api_key="K", amap_base_url="https://restapi.amap.com/v3")


_BJ_RESP = {
    "status": "1",
    "info": "OK",
    "infocode": "10000",
    "count": "1",
    "geocodes": [
        {
            "country": "中国",
            "province": "北京市",
            "city": [],
            "adcode": "110000",
            "location": "116.407526,39.904030",
        }
    ],
}

_EMPTY_RESP = {"status": "1", "info": "OK", "count": "0", "geocodes": []}


@respx.mock
def test_cn_city_returns_geocode_result() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_BJ_RESP)
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    g = p.geocode("北京")
    assert g is not None
    assert g.country == "中国"
    assert g.adcode == "110000"
    assert g.longitude == 116.407526
    assert g.latitude == 39.904030


@respx.mock
def test_empty_geocodes_returns_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json=_EMPTY_RESP)
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    assert p.geocode("Atlantis") is None


@respx.mock
def test_non_cn_country_returns_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "1",
                "info": "OK",
                "count": "1",
                "geocodes": [
                    {
                        "country": "日本",
                        "province": "東京都",
                        "city": [],
                        "adcode": "",
                        "location": "139.6917,35.6895",
                    }
                ],
            },
        )
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    assert p.geocode("Tokyo") is None  # outside CN coverage -> None per spec §8


@respx.mock
def test_malformed_response_returns_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})  # no geocodes key
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    assert p.geocode("X") is None


@respx.mock
def test_api_error_is_swallowed_to_none() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200, json={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        )
    )
    p = AmapGeocodingProvider(AmapHttpClient(_settings()))
    # Geocoding is "soft": upstream API error -> None so callers can fall back.
    assert p.geocode("北京") is None
