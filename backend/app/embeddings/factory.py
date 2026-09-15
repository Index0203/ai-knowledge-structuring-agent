from app.core.config import settings
from app.embeddings.contracts import EmbeddingProvider
from app.embeddings.deterministic import DeterministicEmbeddingProvider


def create_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicEmbeddingProvider(dimensions=settings.embedding_dimensions)
    if provider == "openai":
        from app.embeddings.openai_embeddings import create_openai_embedding_provider

        return create_openai_embedding_provider()
    raise RuntimeError(f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'.")


def describe_embedding_provider() -> str:
    """Provider name without constructing the client (used by status endpoints)."""
    provider = settings.embedding_provider.strip().lower()
    if provider == "deterministic":
        return f"deterministic-hashing-{settings.embedding_dimensions}"
    if provider == "openai":
        return settings.openai_embedding_model or "openai-embedding-unspecified"
    return f"unsupported:{provider}"
