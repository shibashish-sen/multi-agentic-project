"""Flight MCP server — exposes search_flights as an MCP tool over stdio.
Returns a structured FlightSearchResult (not a formatted string).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import FlightOption, FlightSearchResult  # noqa: E402

load_dotenv()

mcp = FastMCP("flight-service")

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")


def _parse_flights(flight_list, origin: str, destination: str) -> list[FlightOption]:
    options = []
    for f in flight_list:
        flights = f.get("flights", [])
        if not flights:
            continue
        first_leg = flights[0]
        last_leg = flights[-1]
        airlines = [leg.get("airline", "") for leg in flights if leg.get("airline")]
        flight_numbers = [leg.get("flight_number", "") for leg in flights if leg.get("flight_number")]

        total_minutes = f.get("total_duration")
        duration_str = (
            f"{int(total_minutes) // 60}h {int(total_minutes) % 60}m"
            if isinstance(total_minutes, (int, float)) else "N/A"
        )

        raw_data = {
            "airline": " / ".join(dict.fromkeys(airlines)),
            "flight_number": " / ".join(dict.fromkeys(flight_numbers)),
            "origin": first_leg.get("departure_airport", {}).get("name", origin),
            "destination": last_leg.get("arrival_airport", {}).get("name", destination),
            "departure_time": first_leg.get("departure_airport", {}).get("time") or "N/A",
            "arrival_time": last_leg.get("arrival_airport", {}).get("time") or "N/A",
            "duration": duration_str,
            "stops": f.get("stops") or 0,
            "price": f.get("price") or 0,
            "currency": f.get("currency", "USD"),
            # Real booking links need a second SerpApi call with a
            # booking_token — skipped here, this endpoint is price-only.
            "link": None,
        }
        try:
            options.append(FlightOption.model_validate(raw_data))
        except ValidationError:
            continue
    return options


@mcp.tool()
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    flight_type: str = "2",
) -> FlightSearchResult:
    """Search Google Flights via SerpApi between two locations.

    Args:
        origin: IATA airport code (3 uppercase letters), e.g. 'BLR'.
        destination: IATA airport code (3 uppercase letters), e.g. 'MAA'.
        departure_date: Date in YYYY-MM-DD format.
        return_date: Return date in YYYY-MM-DD format. Omit for one-way.
        adults: Number of adult passengers (1-9).
        flight_type: '2' for one-way, '1' for round-trip.
    """
    base = FlightSearchResult(
        origin=origin, destination=destination,
        departure_date=departure_date, return_date=return_date,
    )

    if not SERPAPI_KEY:
        base.error = "SERPAPI_API_KEY is not set."
        return base

    try:
        dep_dt = datetime.strptime(departure_date, "%Y-%m-%d")
        if dep_dt < datetime.now():
            base.error = "Departure date must be today or later."
            return base
    except ValueError:
        base.error = "Invalid departure date — use YYYY-MM-DD."
        return base

    if return_date:
        try:
            ret_dt = datetime.strptime(return_date, "%Y-%m-%d")
            if ret_dt <= dep_dt:
                base.error = "Return date must be after departure date."
                return base
        except ValueError:
            base.error = "Invalid return date — use YYYY-MM-DD."
            return base

    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "currency": "USD",
        "hl": "en",
        "type": flight_type,
        "adults": adults,
    }
    if return_date and flight_type == "1":
        params["return_date"] = return_date
    params["api_key"] = SERPAPI_KEY

    try:
        resp = httpx.get("https://serpapi.com/search", params=params, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        base.error = f"SerpApi request failed (HTTP {e.response.status_code}): {e.response.text[:300]}"
        return base
    except httpx.TimeoutException:
        base.error = "Search timed out — please try again."
        return base

    data = resp.json()
    if "error" in data:
        base.error = f"SerpApi Error: {data['error']}"
        return base

    best_flights = data.get("best_flights", [])
    other_flights = data.get("other_flights", [])
    outbound_flights = (best_flights + other_flights)[:5]

    if not outbound_flights:
        base.error = f"No flights found for {origin} -> {destination} on {departure_date}."
        return base

    base.outbound = _parse_flights(outbound_flights, origin, destination)
    if not base.outbound:
        base.error = (
            f"Flights were found ({len(outbound_flights)} raw entries) but "
            f"none could be parsed. Sample raw entry keys: "
            f"{list(outbound_flights[0].keys()) if outbound_flights else 'none'}"
        )
        return base

    if flight_type == "1" and return_date:
        dep_token = outbound_flights[0].get("departure_token")
        if dep_token:
            return_params = dict(params)
            return_params["departure_token"] = dep_token
            try:
                ret_resp = httpx.get("https://serpapi.com/search", params=return_params, timeout=15.0)
                ret_resp.raise_for_status()
                ret_data = ret_resp.json()
                ret_flights = (ret_data.get("best_flights", []) + ret_data.get("other_flights", []))[:5]
                base.return_flights = _parse_flights(ret_flights, destination, origin)
            except (httpx.HTTPStatusError, httpx.TimeoutException):
                pass  # outbound still populated; return leg fetch just failed

    return base


if __name__ == "__main__":
    mcp.run(transport="stdio")