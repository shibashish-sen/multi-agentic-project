"""Stdio MCP client for the flight service. Returns a structured
FlightSearchResult (parsed from structuredContent) instead of raw text.
"""
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import FlightSearchResult  # noqa: E402

SERVICE_PATH = Path(__file__).resolve().parent.parent / "services" / "flight_service.py"

_server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(SERVICE_PATH)],
    env=os.environ.copy(),
)


async def call_flight_tool(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    adults: int = 1,
    flight_type: str = "2",
) -> FlightSearchResult:
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_flights",
                arguments={
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "adults": adults,
                    "flight_type": flight_type,
                },
            )
            return FlightSearchResult.model_validate(result.structuredContent)