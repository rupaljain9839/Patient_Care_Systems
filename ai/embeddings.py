"""Embedding model wrapper, used by the Chroma vector store for retrieval."""
from chromadb.utils import embedding_functions

from core.config import settings


def get_embedding_function():
    """Returns a Chroma-compatible embedding function using the model set in .env
    (EMBEDDING_MODEL, default BAAI/bge-large-en-v1.5). The first call downloads
    the model, which can take a while — subsequent calls reuse the local cache.
    If downloads are too slow, switch EMBEDDING_MODEL to a smaller model like
    sentence-transformers/all-MiniLM-L6-v2 in your .env."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)