# retrieval/retriever.py
from retrieval.vector_store import get_vector_store

def get_retriever(k: int = 5):
    return get_vector_store().as_retriever(search_kwargs={"k": k})