# retrieval/vector_store.py
"""Read-only connection to the Supabase pgvector store. Writes are
owned entirely by the separate ingestion pipeline project."""
from functools import lru_cache
from langchain_postgres import PGVector
from retrieval.config import DATABASE_URL, COLLECTION_NAME
from retrieval.embeddings import get_embedding_model

@lru_cache(maxsize=1)
def get_vector_store() -> PGVector:
    return PGVector(
        embeddings=get_embedding_model(),
        collection_name=COLLECTION_NAME,
        connection=DATABASE_URL,
        use_jsonb=True,
    )