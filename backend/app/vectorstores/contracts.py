from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class VectorRecord:
    chunk_id: UUID
    document_id: UUID
    embedding: list[float]
    text: str
    metadata: dict[str, str | int | float | bool]


@dataclass(frozen=True)
class VectorMatch:
    chunk_id: UUID
    score: float


class VectorStore(Protocol):
    """Derived retrieval index. PostgreSQL remains the source of truth."""

    def upsert(self, records: list[VectorRecord]) -> None:
        """Insert or replace vectors for the given chunks."""

    def query(self, *, document_id: UUID, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        """Return the closest chunks inside one document, best first."""

    def delete_document(self, document_id: UUID) -> None:
        """Remove every vector belonging to a document."""
