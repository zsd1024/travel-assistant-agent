"""POIProvider Protocol. Implementations: providers.mock.poi, providers.amap.poi."""
from typing import Protocol

from travel_assistant.models import Activity


class POIProvider(Protocol):
    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        ...
