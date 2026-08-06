"""Hotel MCP server — exposes search_hotels as an MCP tool over stdio,
via SerpApi's Google Hotels engine (same SERPAPI_API_KEY as flight_service).
Returns a structured HotelSearchResult (not a formatted string).
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
from schemas import HotelOption, HotelSearchResult  # noqa: E402

load_dotenv()

mcp = FastMCP("hotel-service")

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")


@mcp.tool()
def search_hotels(
    destination: str,
    check_in: str,
    check_out: str,
    adults: int = 1,
) -> HotelSearchResult:
    """Search hotels via SerpApi's Google Hotels engine for a destination
    and date range.

    Args:
        destination: City or area name, e.g. 'Chennai', 'Paris'.
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        adults: Number of adult guests (1-9).
    """
    base = HotelSearchResult(destination=destination, check_in=check_in, check_out=check_out)

    if not SERPAPI_KEY:
        base.error = "SERPAPI_API_KEY is not set."
        return base

    try:
        in_dt = datetime.strptime(check_in, "%Y-%m-%d")
        out_dt = datetime.strptime(check_out, "%Y-%m-%d")
        if out_dt <= in_dt:
            base.error = "check_out must be after check_in."
            return base
    except ValueError:
        base.error = "Invalid date format — use YYYY-MM-DD."
        return base

    params = {
        "engine": "google_hotels",
        "q": destination,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": adults,
        "currency": "USD",
        "hl": "en",
        "gl": "us",
        "api_key": SERPAPI_KEY,
    }

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

    properties = data.get("properties", [])
    if not properties:
        base.error = f"No hotels found for {destination} on {check_in} to {check_out}."
        return base

    nights = (out_dt - in_dt).days

    parsed = []
    for p in properties:
        rate = p.get("rate_per_night", {}) or {}
        price_per_night = rate.get("extracted_lowest") or 0
        raw_data = {
            "name": p.get("name", "Unknown"),
            "hotel_class": p.get("hotel_class"),
            "rating": p.get("overall_rating"),
            "price_per_night": price_per_night,
            # Computed ourselves rather than trusting SerpApi's total_rate,
            # which can reflect taxes/fees or a different date assumption
            # than what we actually asked for — this keeps cost math
            # self-consistent with what we display.
            "total_price": round(price_per_night * nights, 2),
            "currency": "USD",
            "amenities": p.get("amenities", [])[:8],
            "link": p.get("link"),
        }
        try:
            option = HotelOption.model_validate(raw_data)
            if option.total_price > 0:
                parsed.append(option)
        except ValidationError:
            continue

    if not parsed:
        base.error = "Hotels were found but could not be parsed."
        return base

    # Spread across the price range (cheapest -> priciest) rather than
    # whatever order the API happened to return — gives a budget/mid/luxury
    # spread instead of 5 near-duplicates, and feeds the future budget tier.
    parsed.sort(key=lambda h: h.total_price)
    n = len(parsed)
    if n <= 5:
        hotels = parsed
    else:
        indices = sorted(set(round(i * (n - 1) / 4) for i in range(5)))
        hotels = [parsed[i] for i in indices]

    base.hotels = hotels
    return base


if __name__ == "__main__":
    mcp.run(transport="stdio")