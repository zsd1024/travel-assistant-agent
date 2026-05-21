"""AmapWeatherProvider — per-call mock fallback for non-CN / upstream errors."""
from __future__ import annotations

import logging

from travel_assistant.providers.amap._client import AmapHttpClient
from travel_assistant.providers.amap._errors import AmapError
from travel_assistant.providers.geocoding import GeocodingProvider
from travel_assistant.providers.weather import WeatherProvider

_LOG = logging.getLogger("travel_assistant.providers.amap.weather")


class AmapWeatherProvider:
    def __init__(
        self,
        client: AmapHttpClient,
        geocoding: GeocodingProvider,
        fallback: WeatherProvider,
    ) -> None:
        self._client = client
        self._geo = geocoding
        self._fallback = fallback

    def forecast(self, city: str, days: int, *, seed: int = 0) -> list[str]:
        if days <= 0:
            return []
        geo = self._geo.geocode(city)
        if geo is None or geo.country != "中国" or not geo.adcode:
            _LOG.info(
                "[amap] city=%s outside CN coverage; falling back to mock for this call",
                city,
            )
            return self._fallback.forecast(city, days, seed=seed)
        try:
            data = self._client.get(
                "weather/weatherInfo", {"city": geo.adcode, "extensions": "all"}
            )
        except AmapError as e:
            _LOG.info(
                "[amap] city=%s upstream error (%s); falling back to mock for this call",
                city, type(e).__name__,
            )
            return self._fallback.forecast(city, days, seed=seed)

        forecasts = data.get("forecasts") or []
        if not forecasts:
            _LOG.info(
                "[amap] city=%s empty forecast; falling back to mock for this call",
                city,
            )
            return self._fallback.forecast(city, days, seed=seed)
        casts = forecasts[0].get("casts") or []
        out = [(c.get("dayweather") or "").strip() for c in casts[:days] if c.get("dayweather")]
        # If Amap returns fewer days than requested, pad with mock for the
        # remaining days (rare; explicit per spec §8 "graceful").
        if len(out) < days:
            extra = self._fallback.forecast(city, days - len(out), seed=seed)
            out.extend(extra)
        return out
