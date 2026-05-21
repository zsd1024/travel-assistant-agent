"""AmapPOIProvider — per-call mock fallback for non-CN / upstream errors."""
from __future__ import annotations

import logging
from typing import Any

from travel_assistant.models import Activity
from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.poi import POIProvider

_LOG = logging.getLogger("travel_assistant.providers.amap.poi")

# Narrow interest -> Amap POI category (typecode) mapping for V1. Other
# interests fall through to keyword search.
_INTEREST_TYPES: dict[str, str] = {
    "food": "050000",
    "city walks": "110000",
    "history": "110200",
}


class AmapPOIProvider:
    def __init__(
        self,
        client: AmapHttpClient,
        geocoding: GeocodingProvider,
        fallback: POIProvider,
    ) -> None:
        self._client = client
        self._geo = geocoding
        self._fallback = fallback

    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        geo = self._geo.geocode(city)
        if geo is None or geo.country != "中国" or not geo.adcode:
            _LOG.info(
                "[amap] city=%s outside CN coverage; falling back to mock for this call",
                city,
            )
            return self._fallback.search(city, interests, seed=seed)

        try:
            return self._search_amap(city, geo.adcode, interests)
        except AmapError as e:
            _LOG.info(
                "[amap] city=%s upstream error (%s); falling back to mock for this call",
                city, type(e).__name__,
            )
            return self._fallback.search(city, interests, seed=seed)

    def _search_amap(
        self, city: str, adcode: str, interests: list[str]
    ) -> list[Activity]:
        effective = [i for i in interests if i.strip()] or ["sightseeing"]
        seen_ids: set[str] = set()
        out: list[Activity] = []
        for interest in effective:
            params: dict[str, Any] = {
                "city": adcode,
                "citylimit": "true",
                "offset": "5",
                "page": "1",
            }
            typecode = _INTEREST_TYPES.get(interest.lower())
            if typecode:
                params["types"] = typecode
            else:
                params["keywords"] = interest
            data = self._client.get("place/text", params)
            for poi in data.get("pois") or []:
                pid = str(poi.get("id") or poi.get("name"))
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                name = (poi.get("name") or "").strip()
                if not name:
                    continue
                category = interest if typecode else "sightseeing"
                out.append(
                    Activity(
                        name=f"{name} ({city})",
                        category=category,
                        notes=(poi.get("address") or "").strip(),
                    )
                )
        return out
