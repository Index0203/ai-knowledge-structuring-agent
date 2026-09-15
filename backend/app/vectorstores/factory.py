from app.vectorstores.chroma_vector_store import create_chroma_vector_store
from app.vectorstores.contracts import VectorStore


def create_vector_store() -> VectorStore:
    """ChromaDB is the derived retrieval index; PostgreSQL stays the source of truth."""
    return create_chroma_vector_store()
