from typing import Protocol


class EmbeddingProvider(Protocol):
    """Turns text into vectors for the retrieval index."""

    name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed stored content blocks."""

    def embed_query(self, text: str) -> list[float]:
        """Embed a retrieval query with the same vector space."""
