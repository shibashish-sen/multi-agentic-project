"""Weather MCP server — exposes get_weather and get_historical_weather_average
as MCP tools over stdio. Returns structured Pydantic models (not formatted
strings) so downstream code can consume the data without an LLM parsing it
back out of prose.
"""
import sys
import statistics
from datetime import datetime
from pathlib import Path

import httpx
from pydantic import ValidationError
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import WeatherResult, HistoricalWeatherEstimate  # noqa: E402

mcp = FastMCP("weather-service")

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def _geocode(location: str):
    """Geocode a location. Accepts 'City' or 'City, Country' — Open-Meteo's
    name search only matches on the city part cleanly, so we split off any
    country and use it only to disambiguate between multiple name matches
    (e.g. 'Bangalore' alone can resolve to a town in Pakistan instead of
    Bengaluru, India)."""
    if "," in location:
        city_part, country_hint = (p.strip() for p in location.split(",", 1))
    else:
        city_part, country_hint = location.strip(), None

    geo = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city_part, "count": 10, "format": "json"},
    ).json()
    results = geo.get("results")
    if not results:
        return None

    if country_hint:
        for r in results:
            if country_hint.lower() in (r.get("country") or "").lower() or \
               country_hint.lower() == (r.get("country_code") or "").lower():
                return r

    return results[0]


@mcp.tool()
def get_weather(location: str, date: str, time: str) -> WeatherResult:
    """Fetch the weather forecast for a location at a specific date and time.
    Only covers dates within 16 days from today — dates further out will
    return an error field explaining that, use get_historical_weather_average
    instead.

    Args:
        location: City name, e.g. 'Tokyo', 'New York'.
        date: Date in YYYY-MM-DD format.
        time: Time in HH:MM 24-hour format.
    """
    place = _geocode(location)
    if place is None:
        return WeatherResult(
            location_name=location, country="", date=date, time=time,
            condition="", temperature_c=0, feels_like_c=0, humidity_pct=0,
            precipitation_mm=0, precipitation_chance_pct=0, wind_speed_kmh=0,
            wind_direction_deg=0, error=f"Location not found: {location}",
        )
    lat, lon = place["latitude"], place["longitude"]

    try:
        target = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return WeatherResult(
            location_name=place["name"], country=place.get("country", ""),
            date=date, time=time, condition="", temperature_c=0,
            feels_like_c=0, humidity_pct=0, precipitation_mm=0,
            precipitation_chance_pct=0, wind_speed_kmh=0, wind_direction_deg=0,
            error="Invalid format — use YYYY-MM-DD for date and HH:MM for time.",
        )

    wx = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "precipitation,precipitation_probability,weather_code,"
                "wind_speed_10m,wind_direction_10m"
            ),
            "timezone": "auto",
            "forecast_days": 16,
        },
    ).json()

    hourly = wx.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return WeatherResult(
            location_name=place["name"], country=place.get("country", ""),
            date=date, time=time, condition="", temperature_c=0,
            feels_like_c=0, humidity_pct=0, precipitation_mm=0,
            precipitation_chance_pct=0, wind_speed_kmh=0, wind_direction_deg=0,
            error="No forecast data available.",
        )

    best_idx = min(
        range(len(times)),
        key=lambda i: abs((datetime.fromisoformat(times[i]) - target).total_seconds()),
    )

    if abs((datetime.fromisoformat(times[best_idx]) - target).total_seconds()) > 3600:
        last_available = times[-1][:10]
        if target > datetime.fromisoformat(times[-1]):
            err = (
                f"No forecast available for {date} — Open-Meteo only forecasts "
                f"16 days ahead (through {last_available}). Use "
                f"get_historical_weather_average instead."
            )
        else:
            err = f"No data within 1 hour of {date} {time} for {place['name']}."
        return WeatherResult(
            location_name=place["name"], country=place.get("country", ""),
            date=date, time=time, condition="", temperature_c=0,
            feels_like_c=0, humidity_pct=0, precipitation_mm=0,
            precipitation_chance_pct=0, wind_speed_kmh=0, wind_direction_deg=0,
            error=err,
        )

    try:
        return WeatherResult(
            location_name=place["name"],
            country=place.get("country", "Unknown"),
            date=date,
            time=time,
            condition=WEATHER_CODES.get(
                hourly["weather_code"][best_idx], f"Code {hourly['weather_code'][best_idx]}"
            ),
            temperature_c=hourly["temperature_2m"][best_idx],
            feels_like_c=hourly["apparent_temperature"][best_idx],
            humidity_pct=hourly["relative_humidity_2m"][best_idx],
            precipitation_mm=hourly["precipitation"][best_idx],
            precipitation_chance_pct=hourly["precipitation_probability"][best_idx],
            wind_speed_kmh=hourly["wind_speed_10m"][best_idx],
            wind_direction_deg=hourly["wind_direction_10m"][best_idx],
        )
    except ValidationError as e:
        return WeatherResult(
            location_name=place["name"], country=place.get("country", ""),
            date=date, time=time, condition="", temperature_c=0,
            feels_like_c=0, humidity_pct=0, precipitation_mm=0,
            precipitation_chance_pct=0, wind_speed_kmh=0, wind_direction_deg=0,
            error=f"Failed to parse weather data from API: {e}",
        )


@mcp.tool()
def get_historical_weather_average(
    location: str, date: str, years_back: int = 5
) -> HistoricalWeatherEstimate:
    """Estimate typical weather for a location on a given calendar date,
    based on historical averages from the past N years. Use this for dates
    more than 16 days from today. This is a historical average, NOT a
    forecast.

    Args:
        location: City name, e.g. 'Tokyo', 'New York'.
        date: Target date in YYYY-MM-DD format. Only month/day is used.
        years_back: How many past years to average over (default 5).
    """
    place = _geocode(location)
    if place is None:
        return HistoricalWeatherEstimate(
            location_name=location, country="", date=date, years_averaged=0,
            typical_high_c=0, typical_low_c=0, avg_precipitation_mm=0,
            rainy_years=0, error=f"Location not found: {location}",
        )
    lat, lon = place["latitude"], place["longitude"]

    try:
        target = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return HistoricalWeatherEstimate(
            location_name=place["name"], country=place.get("country", ""),
            date=date, years_averaged=0, typical_high_c=0, typical_low_c=0,
            avg_precipitation_mm=0, rainy_years=0,
            error="Invalid date format — use YYYY-MM-DD.",
        )

    current_year = datetime.now().year
    temps_max, temps_min, precip = [], [], []

    for offset in range(1, years_back + 1):
        base_year = target.year if target.year < current_year else current_year
        year = base_year - offset
        try:
            hist_date = target.replace(year=year)
        except ValueError:
            hist_date = target.replace(year=year, day=28)
        date_str = hist_date.strftime("%Y-%m-%d")

        resp = httpx.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": date_str,
                "end_date": date_str,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "auto",
            },
            timeout=15.0,
        )
        if resp.status_code != 200:
            continue
        daily = resp.json().get("daily", {})
        if daily.get("temperature_2m_max"):
            tmax, tmin, psum = (
                daily["temperature_2m_max"][0],
                daily["temperature_2m_min"][0],
                daily["precipitation_sum"][0],
            )
            if tmax is not None:
                temps_max.append(tmax)
            if tmin is not None:
                temps_min.append(tmin)
            if psum is not None:
                precip.append(psum)

    if not temps_max:
        return HistoricalWeatherEstimate(
            location_name=place["name"], country=place.get("country", ""),
            date=date, years_averaged=0, typical_high_c=0, typical_low_c=0,
            avg_precipitation_mm=0, rainy_years=0,
            error=f"No historical data available for {place['name']} around {date}.",
        )

    return HistoricalWeatherEstimate(
        location_name=place["name"],
        country=place.get("country", ""),
        date=date,
        years_averaged=len(temps_max),
        typical_high_c=round(statistics.mean(temps_max), 1),
        typical_low_c=round(statistics.mean(temps_min), 1),
        avg_precipitation_mm=round(statistics.mean(precip), 1) if precip else 0.0,
        rainy_years=sum(1 for p in precip if p > 1.0),
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")