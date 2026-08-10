# retrieval/embeddings.py
from functools import lru_cache
from langchain_huggingface import HuggingFaceEmbeddings
from retrieval.config import EMBEDDING_MODEL_NAME, EMBEDDING_DEVICE

@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": EMBEDDING_DEVICE},
    )