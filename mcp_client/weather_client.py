"""Stdio MCP client for the weather service. Returns structured Pydantic
models (parsed from structuredContent) instead of raw text.
"""
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import WeatherResult, HistoricalWeatherEstimate  # noqa: E402

SERVICE_PATH = Path(__file__).resolve().parent.parent / "services" / "weather_service.py"

_server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(SERVICE_PATH)],
    env=os.environ.copy(),
)


async def call_weather_tool(location: str, date: str, time: str) -> WeatherResult:
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_weather",
                arguments={"location": location, "date": date, "time": time},
            )
            return WeatherResult.model_validate(result.structuredContent)


async def call_historical_weather_tool(
    location: str, date: str, years_back: int = 5
) -> HistoricalWeatherEstimate:
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_historical_weather_average",
                arguments={"location": location, "date": date, "years_back": years_back},
            )
            return HistoricalWeatherEstimate.model_validate(result.structuredContent)