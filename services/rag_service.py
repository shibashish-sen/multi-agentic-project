"""RAG MCP server — exposes search_itinerary as an MCP tool over stdio.
Pure retrieval only: returns top-k chunks, no LLM call, no cost/attraction
extraction. Returns a structured ItinerarySearchResult (not raw text).
"""
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import ItineraryChunk, ItinerarySearchResult  # noqa: E402
from retrieval.config import DATABASE_URL  # noqa: E402
from retrieval.retriever import get_retriever  # noqa: E402

load_dotenv()

mcp = FastMCP("rag-service")


@mcp.tool()
def search_itinerary(query: str, k: int = 5) -> ItinerarySearchResult:
    """Retrieve top-k relevant travel/itinerary chunks from the Supabase
    pgvector knowledge base.

    Args:
        query: Natural-language search query, e.g. 'things to do in Chennai'.
        k: Number of chunks to retrieve (default 5).
    """
    base = ItinerarySearchResult(query=query)

    if not DATABASE_URL:
        base.error = "DATABASE_URL is not set."
        return base

    try:
        retriever = get_retriever(k=k)
        docs = retriever.invoke(query)
    except Exception as e:
        base.error = f"Retrieval failed: {e}"
        return base

    base.results = [
        ItineraryChunk(
            content=doc.page_content,
            city=doc.metadata.get("city"),
            country=doc.metadata.get("country"),
            region=doc.metadata.get("region"),
            source=doc.metadata.get("source"),
            chunk_index=doc.metadata.get("chunk_index"),
        )
        for doc in docs
    ]
    return base


if __name__ == "__main__":
    mcp.run(transport="stdio")