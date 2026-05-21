import logging

import httpx
import pytest
import respx

from travel_assistant.config import Settings
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import (
    AmapApiError,
    AmapTransientError,
)


def _settings() -> Settings:
    return Settings(
        amap_api_key="SECRET-KEY-123",
        amap_base_url="https://restapi.amap.com/v3",
        amap_request_timeout_s=2.0,
        amap_max_retries=2,
    )


@respx.mock
def test_get_injects_key_and_returns_json() -> None:
    route = respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200, json={"status": "1", "info": "OK", "geocodes": []}
        )
    )
    client = AmapHttpClient(_settings())
    data = client.get("geocode/geo", {"address": "Beijing"})

    assert data["status"] == "1"
    assert route.called
    sent_url = route.calls.last.request.url
    assert "key=SECRET-KEY-123" in str(sent_url)
    assert "output=JSON" in str(sent_url)


@respx.mock
def test_get_redacts_key_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})
    )
    caplog.set_level(logging.DEBUG, logger="travel_assistant.providers.amap")
    AmapHttpClient(_settings()).get("geocode/geo", {"address": "Beijing"})
    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert "SECRET-KEY-123" not in full_log
    assert "key=***" in full_log or "key=REDACTED" in full_log


@respx.mock
def test_get_caches_repeated_call() -> None:
    route = respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})
    )
    client = AmapHttpClient(_settings())
    a = client.get("geocode/geo", {"address": "Beijing"})
    b = client.get("geocode/geo", {"address": "Beijing"})
    assert a == b
    assert route.call_count == 1  # second call served from cache


@respx.mock
def test_get_cache_miss_on_different_params() -> None:
    route = respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(200, json={"status": "1", "info": "OK"})
    )
    client = AmapHttpClient(_settings())
    client.get("geocode/geo", {"address": "Beijing"})
    client.get("geocode/geo", {"address": "Shanghai"})
    assert route.call_count == 2


@respx.mock
def test_retry_on_5xx_then_success() -> None:
    route = respx.get("https://restapi.amap.com/v3/place/text").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"status": "1", "info": "OK", "pois": []}),
        ]
    )
    client = AmapHttpClient(_settings())
    data = client.get("place/text", {"keywords": "x"})
    assert data["status"] == "1"
    assert route.call_count == 2


@respx.mock
def test_no_retry_on_4xx_raises() -> None:
    route = respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(400, text="bad request")
    )
    client = AmapHttpClient(_settings())
    with pytest.raises(AmapApiError):
        client.get("place/text", {"keywords": "x"})
    assert route.call_count == 1


@respx.mock
def test_persistent_5xx_eventually_raises_transient() -> None:
    respx.get("https://restapi.amap.com/v3/place/text").mock(
        return_value=httpx.Response(503)
    )
    with pytest.raises(AmapTransientError):
        AmapHttpClient(_settings()).get("place/text", {"keywords": "x"})


@respx.mock
def test_amap_status_not_1_raises_api_error() -> None:
    respx.get("https://restapi.amap.com/v3/geocode/geo").mock(
        return_value=httpx.Response(
            200, json={"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        )
    )
    with pytest.raises(AmapApiError, match="INVALID_USER_KEY"):
        AmapHttpClient(_settings()).get("geocode/geo", {"address": "Beijing"})
