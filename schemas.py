"""Shared schemas for the travel planner — structured form input, itinerary
data (from RAG), and cost estimation. Used across the orchestrator graph
and services so every node speaks the same typed contract instead of
passing around formatted strings.
"""
from datetime import date as Date
from enum import Enum

from pydantic import BaseModel, Field


# ── Trip input (from the form) ───────────────────────────────────────

class BudgetTier(str, Enum):
    budget = "budget"
    mid = "mid"
    luxury = "luxury"


class TripRequest(BaseModel):
    """What the form submits. origin/destination come from dropdowns (IATA
    codes), dates from date pickers — no free-text parsing needed."""
    origin: str = Field(description="IATA airport code, e.g. 'BLR'")
    destination: str = Field(description="IATA airport code, e.g. 'MAA'")
    departure_date: Date
    return_date: Date | None = None
    adults: int = Field(default=1, ge=1, le=9)
    budget_tier: BudgetTier = BudgetTier.mid  # wired up later (point 4)

    @property
    def nights(self) -> int:
        if not self.return_date:
            return 0
        return (self.return_date - self.departure_date).days

    @property
    def flight_type(self) -> str:
        return "1" if self.return_date else "2"


# ── Itinerary / RAG output ───────────────────────────────────────────

class Attraction(BaseModel):
    name: str
    description: str
    avg_cost_usd: float | None = None
    category: str | None = None  # e.g. 'museum', 'outdoor', 'nightlife'


class MealCostEstimate(BaseModel):
    tier: BudgetTier
    avg_cost_per_meal_usd: float


class ItineraryData(BaseModel):
    """Structured result from the RAG lookup — top-5 nearest embeddings,
    parsed into typed rows instead of a text blob, so cost math doesn't
    need another LLM call to extract numbers back out of prose."""
    destination: str
    attractions: list[Attraction]
    meal_costs: list[MealCostEstimate]


# ── Weather (structured — no more formatted-string returns) ─────────

class WeatherResult(BaseModel):
    location_name: str
    country: str
    date: str
    time: str
    condition: str
    temperature_c: float
    feels_like_c: float
    humidity_pct: int
    precipitation_mm: float
    precipitation_chance_pct: int
    wind_speed_kmh: float
    wind_direction_deg: int
    error: str | None = None


class HistoricalWeatherEstimate(BaseModel):
    location_name: str
    country: str
    date: str
    years_averaged: int
    typical_high_c: float
    typical_low_c: float
    avg_precipitation_mm: float
    rainy_years: int
    note: str = "Historical average, not an exact forecast."
    error: str | None = None


# ── Flights (structured) ─────────────────────────────────────────────

class FlightOption(BaseModel):
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: int
    price: float
    currency: str
    link: str | None = None


class FlightSearchResult(BaseModel):
    origin: str
    destination: str
    departure_date: str
    return_date: str | None = None
    outbound: list[FlightOption] = []
    return_flights: list[FlightOption] = []
    error: str | None = None

    @property
    def cheapest_outbound(self) -> FlightOption | None:
        return min(self.outbound, key=lambda f: f.price, default=None)

    @property
    def cheapest_return(self) -> FlightOption | None:
        return min(self.return_flights, key=lambda f: f.price, default=None)


# ── Hotels (structured) ──────────────────────────────────────────────

class HotelOption(BaseModel):
    name: str
    hotel_class: str | None = None
    rating: float | None = None
    price_per_night: float
    total_price: float
    currency: str
    amenities: list[str] = []
    link: str | None = None


class HotelSearchResult(BaseModel):
    destination: str
    check_in: str
    check_out: str
    hotels: list[HotelOption] = []
    error: str | None = None

    @property
    def cheapest(self) -> HotelOption | None:
        return min(self.hotels, key=lambda h: h.total_price, default=None)


class CostLineItem(BaseModel):
    label: str
    amount: float
    currency: str = "USD"
    note: str | None = None  # e.g. "historical average, not exact"


class TripCostEstimate(BaseModel):
    flights: CostLineItem
    hotel: CostLineItem | None = None
    meals: CostLineItem | None = None
    attractions: CostLineItem | None = None

    @property
    def total(self) -> float:
        items = [self.flights, self.hotel, self.meals, self.attractions]
        return sum(i.amount for i in items if i is not None)

    def format(self) -> str:
        lines = [f"  {i.label:<12}: {i.currency} {i.amount:,.2f}" for i in
                  [self.flights, self.hotel, self.meals, self.attractions] if i]
        lines.append(f"  {'TOTAL':<12}: USD {self.total:,.2f}")
        return "\n".join(lines)