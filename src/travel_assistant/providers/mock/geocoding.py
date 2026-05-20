from travel_assistant.models import GeocodeResult

# Minimal CN-city whitelist for offline tests / demos. Real Amap geocoding is
# used in production runs via providers.amap.geocoding.
_CN_CITIES: dict[str, GeocodeResult] = {
    "北京": GeocodeResult(
        city="北京", country="中国", province="北京市",
        adcode="110000", longitude=116.407526, latitude=39.904030,
    ),
    "上海": GeocodeResult(
        city="上海", country="中国", province="上海市",
        adcode="310000", longitude=121.473701, latitude=31.230416,
    ),
    "广州": GeocodeResult(
        city="广州", country="中国", province="广东省",
        adcode="440100", longitude=113.264385, latitude=23.129163,
    ),
    "杭州": GeocodeResult(
        city="杭州", country="中国", province="浙江省",
        adcode="330100", longitude=120.155070, latitude=30.274085,
    ),
}
_ALIASES: dict[str, str] = {
    "beijing": "北京",
    "shanghai": "上海",
    "guangzhou": "广州",
    "hangzhou": "杭州",
}


class MockGeocodingProvider:
    """Returns a deterministic GeocodeResult for known CN cities, else None."""

    def geocode(self, city: str) -> GeocodeResult | None:
        key = city.strip()
        if not key:
            return None
        if key in _CN_CITIES:
            return _CN_CITIES[key]
        alias = _ALIASES.get(key.lower())
        if alias:
            return _CN_CITIES[alias]
        return None
