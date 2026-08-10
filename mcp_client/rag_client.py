"""Stdio MCP client for the RAG service. Returns a structured
ItinerarySearchResult (parsed from structuredContent) instead of raw text.
"""
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import ItinerarySearchResult  # noqa: E402

SERVICE_PATH = Path(__file__).resolve().parent.parent / "services" / "rag_service.py"

_server_params = StdioServerParameters(
    command=sys.executable,
    args=[str(SERVICE_PATH)],
    env=os.environ.copy(),
)


async def call_rag_tool(query: str, k: int = 5) -> ItinerarySearchResult:
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_itinerary",
                arguments={"query": query, "k": k},
            )
            return ItinerarySearchResult.model_validate(result.structuredContent)