"""Domain models. Critical fields gate planning (spec §4, §5)."""
from __future__ import annotations

import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ComfortLevel(StrEnum):
    BUDGET = "budget"
    COMFORT = "comfort"
    LUXURY = "luxury"


class MissingField(BaseModel):
    """Focused, data-only clarification info for one missing critical field."""

    field: str
    label: str
    example: str


_CLARIFICATION = {
    "origin": ("Where are you departing from?", "Shanghai"),
    "destination": ("Where do you want to travel to?", "Tokyo"),
    "dates_or_duration": (
        "How long is the trip, or what are the exact dates?",
        "5 days, or 2026-06-01 to 2026-06-05",
    ),
    "comfort_level": (
        "What comfort level do you want?",
        "budget, comfort, or luxury",
    ),
}


class TripRequest(BaseModel):
    origin: str | None = None
    destination: str | None = None
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    duration_days: int | None = None
    party_size: int = 1
    comfort_level: ComfortLevel | None = None
    interests: list[str] = Field(default_factory=list)

    def _has_dates_or_duration(self) -> bool:
        return self.duration_days is not None or (
            self.start_date is not None and self.end_date is not None
        )

    def missing_critical_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.origin:
            missing.append("origin")
        if not self.destination:
            missing.append("destination")
        if not self._has_dates_or_duration():
            missing.append("dates_or_duration")
        if self.comfort_level is None:
            missing.append("comfort_level")
        return missing

    def is_ready_to_plan(self) -> bool:
        return not self.missing_critical_fields()

    def clarification_targets(self) -> list[MissingField]:
        out: list[MissingField] = []
        for f in self.missing_critical_fields():
            label, example = _CLARIFICATION[f]
            out.append(MissingField(field=f, label=label, example=example))
        return out


class Activity(BaseModel):
    name: str
    category: str
    notes: str = ""


class DayPlan(BaseModel):
    day_index: int
    date: datetime.date | None = None
    weather: str = ""
    activities: list[Activity] = Field(default_factory=list)


class FlightOption(BaseModel):
    carrier: str
    depart: str
    arrive: str
    price: float
    currency: str = "USD"


class HotelOption(BaseModel):
    name: str
    area: str
    price_per_night: float
    currency: str = "USD"
    rating: float = 0.0


class BudgetBreakdown(BaseModel):
    currency: str = "USD"
    flights: float = 0.0
    lodging: float = 0.0
    food: float = 0.0
    activities: float = 0.0
    local_transport: float = 0.0
    total: float = 0.0


class TripPlan(BaseModel):
    summary: str
    days: list[DayPlan] = Field(default_factory=list)
    flight_options: list[FlightOption] = Field(default_factory=list)
    hotel_options: list[HotelOption] = Field(default_factory=list)
    transport_notes: str = ""
    budget: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    assumptions: list[str] = Field(default_factory=list)


class UserPreferences(BaseModel):
    user_id: str
    liked_interests: list[str] = Field(default_factory=list)
    preferred_comfort_level: ComfortLevel | None = None
    pace_notes: str = ""
    dietary_notes: str = ""
    home_city: str = ""
