from travel_assistant.models import Activity
from travel_assistant.tools.attractions import find_attractions


class MockPOIProvider:
    """Wraps tools.attractions.find_attractions."""

    def search(
        self, city: str, interests: list[str], *, seed: int = 0
    ) -> list[Activity]:
        return find_attractions(city, interests, seed=seed)
