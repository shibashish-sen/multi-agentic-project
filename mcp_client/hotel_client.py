"""Stdio MCP client for the hotel service. Returns a structured
HotelSearchResult (parsed from structuredContent) instead of raw text.
"""
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import HotelSearchResult  # noqa: E402

SERVICE_PATH = Path(__file__).resolve().parent.parent / "services" / "hotel_service.py"

_server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(SERVICE_PATH)],
    env=os.environ.copy(),
)


async def call_hotel_tool(
    destination: str,
    check_in: str,
    check_out: str,
    adults: int = 1,
) -> HotelSearchResult:
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_hotels",
                arguments={
                    "destination": destination,
                    "check_in": check_in,
                    "check_out": check_out,
                    "adults": adults,
                },
            )
            return HotelSearchResult.model_validate(result.structuredContent)