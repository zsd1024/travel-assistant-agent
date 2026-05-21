"""AmapGeocodingProvider: returns GeocodeResult or None (soft)."""
from __future__ import annotations

import logging

from travel_assistant.models import GeocodeResult
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError

_LOG = logging.getLogger("travel_assistant.providers.amap.geocoding")


class AmapGeocodingProvider:
    def __init__(self, client: AmapHttpClient) -> None:
        self._client = client

    def geocode(self, city: str) -> GeocodeResult | None:
        key = city.strip()
        if not key:
            return None
        try:
            data = self._client.get("geocode/geo", {"address": key})
        except AmapError as e:
            _LOG.info("amap geocoding soft-fail city=%s err=%s", key, type(e).__name__)
            return None

        codes = data.get("geocodes") or []
        if not codes:
            return None
        first = codes[0]
        country = (first.get("country") or "").strip()
        if country != "中国":
            return None
        adcode = (first.get("adcode") or "").strip()
        province = (first.get("province") or "").strip()
        location = (first.get("location") or "").strip()
        lng: float | None = None
        lat: float | None = None
        if "," in location:
            try:
                lng_s, lat_s = location.split(",", 1)
                lng = float(lng_s)
                lat = float(lat_s)
            except ValueError:
                lng = None
                lat = None
        return GeocodeResult(
            city=key,
            country=country,
            province=province,
            adcode=adcode,
            longitude=lng,
            latitude=lat,
        )
