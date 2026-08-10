"""Deterministic travel-planning orchestrator.

Pipeline: structured TripRequest -> (flights + hotel + weather x2 +
itinerary RAG) run in parallel via asyncio.gather -> cost estimate computed
in Python -> ONE optional LLM call to turn everything into a readable
summary. No ReAct loop, no per-tool-call LLM reasoning.
"""
import asyncio
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from mcp_client.weather_client import call_weather_tool, call_historical_weather_tool
from mcp_client.flight_client import call_flight_tool
from mcp_client.hotel_client import call_hotel_tool
from mcp_client.rag_client import call_rag_tool
from airport_lookup import resolve_city, resolve_iata
from schemas import (
    TripRequest,
    FlightSearchResult,
    HotelSearchResult,
    WeatherResult,
    HistoricalWeatherEstimate,
    TripCostEstimate,
    CostLineItem,
)

load_dotenv()

llm = ChatOpenAI(
    model="openai/gpt-4o-mini",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "http://localhost",
        "X-Title": "Travel Orchestrator",
    },
)


async def _weather_for_date(location: str, target_date: date):
    """Pick the right weather tool deterministically — no LLM decision."""
    days_out = (target_date - datetime.now().date()).days
    if 0 <= days_out <= 16:
        return await call_weather_tool(location, target_date.isoformat(), "12:00")
    return await call_historical_weather_tool(location, target_date.isoformat())


def _compute_cost(
    flights: FlightSearchResult | None,
    hotel: HotelSearchResult | None,
) -> TripCostEstimate:
    """All arithmetic happens here, in plain Python — never handed to the
    LLM to compute."""
    flight_amount = 0.0
    if flights:
        if flights.cheapest_outbound:
            flight_amount += flights.cheapest_outbound.price
        if flights.cheapest_return:
            flight_amount += flights.cheapest_return.price

    hotel_line = None
    if hotel and hotel.cheapest:
        hotel_line = CostLineItem(label="Hotel", amount=hotel.cheapest.total_price)

    return TripCostEstimate(
        flights=CostLineItem(label="Flights", amount=flight_amount),
        hotel=hotel_line,
        # meals / attractions plug in once the RAG data is structured
    )


async def plan_trip(request: TripRequest) -> dict:
    checkout = (
        request.return_date.isoformat()
        if request.return_date
        else (request.departure_date + timedelta(days=1)).isoformat()
    )
    # Flights need an IATA code; hotels/weather need a place name. This
    # resolver pair lets TripRequest.origin/destination accept either a
    # code ('MAA') or a city name ('Chennai') and dispatches correctly.
    origin_code = resolve_iata(request.origin)
    destination_code = resolve_iata(request.destination)
    destination_city = resolve_city(request.destination)

    task_map = {
        "flights": call_flight_tool(
            origin_code, destination_code,
            request.departure_date.isoformat(),
            request.return_date.isoformat() if request.return_date else None,
            request.adults, request.flight_type,
        ),
        "hotel": call_hotel_tool(
            destination_city, request.departure_date.isoformat(),
            checkout, request.adults,
        ),
        "weather_departure": _weather_for_date(destination_city, request.departure_date),
        "itinerary": call_rag_tool(f"things to do, attractions, food in {destination_city}"),
    }
    if request.return_date:
        task_map["weather_return"] = _weather_for_date(destination_city, request.return_date)

    keys = list(task_map.keys())
    results = await asyncio.gather(*task_map.values(), return_exceptions=True)
    r = dict(zip(keys, results))

    for k, v in r.items():
        if isinstance(v, Exception):
            print(f"[warning] {k} failed: {v}")
            r[k] = None

    cost = _compute_cost(r.get("flights"), r.get("hotel"))

    return {**r, "cost_estimate": cost}


async def summarize(request: TripRequest, results: dict) -> str:
    """The one optional LLM call — narrative polish only, no arithmetic,
    no tool-selection reasoning. Skip this function entirely if you'd
    rather render the structured data directly in a UI."""
    parts = [
        f"Trip: {request.origin} -> {request.destination}, "
        f"{request.departure_date} to {request.return_date or 'one-way'}, "
        f"{request.adults} adult(s), budget tier: {request.budget_tier.value}",
        f"\nFlights:\n{results['flights'].model_dump_json(indent=2) if results.get('flights') else 'unavailable'}",
        f"\nHotel:\n{results['hotel'].model_dump_json(indent=2) if results.get('hotel') else 'unavailable'}",
        f"\nWeather (departure):\n{results['weather_departure'].model_dump_json(indent=2) if results.get('weather_departure') else 'unavailable'}",
    ]
    if results.get("weather_return"):
        parts.append(f"\nWeather (return):\n{results['weather_return'].model_dump_json(indent=2)}")
    parts.append(f"\nItinerary context:\n{results['itinerary'].model_dump_json(indent=2) if results.get('itinerary') else 'unavailable'}")
    parts.append(f"\nCost estimate (already computed — report these numbers exactly, do not recalculate):\n{results['cost_estimate'].format()}")

    prompt = (
        "Write a concise, well-organized travel briefing from this structured "
        "trip data. List ALL flight and hotel options provided (not just the "
        "cheapest) so the user can compare price ranges — do not omit any. "
        "Use the cost numbers exactly as given — do not recompute them. Note "
        "clearly which weather figures are real forecasts vs. historical "
        "averages. Include a 'Things to Do' section synthesized from the "
        "itinerary context chunks below — cover attractions, food, and "
        "budget tips relevant to the destination. If itinerary context is "
        "unavailable or has no results, omit that section rather than "
        "inventing content.\n\n" + "\n".join(parts)
    )

    response = await llm.ainvoke(prompt)
    return response.content


async def main():
    # Demo trip — this is what a structured form submission becomes.
    request = TripRequest(
        origin="Mumbai",
        destination="New Delhi",
        departure_date=date(2026, 8, 15),
        return_date=date(2026, 8, 20),
        adults=1,
    )
    results = await plan_trip(request)
    summary = await summarize(request, results)
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())