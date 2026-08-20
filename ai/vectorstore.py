"""Persistent Chroma vector store for the SmartCare AI knowledge base."""
import chromadb

from core.config import settings
from ai.embeddings import get_embedding_function

_client = None
_collection = None


def get_collection():
    """Lazily creates (once per process) a persistent Chroma collection at
    CHROMA_DIR, named KB_COLLECTION — both configurable via .env."""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_dir)
        _collection = _client.get_or_create_collection(
            name=settings.kb_collection,
            embedding_function=get_embedding_function(),
        )
    return _collection