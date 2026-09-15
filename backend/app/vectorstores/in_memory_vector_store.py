"""In-memory vector store used by tests and by callers that must not need Chroma."""

import math
from uuid import UUID

from app.vectorstores.contracts import VectorMatch, VectorRecord


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._records: dict[UUID, VectorRecord] = {}

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._records[record.chunk_id] = record

    def query(self, *, document_id: UUID, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        if limit <= 0:
            return []
        scored = [
            VectorMatch(chunk_id=record.chunk_id, score=_cosine_similarity(query_embedding, record.embedding))
            for record in self._records.values()
            if record.document_id == document_id
        ]
        scored.sort(key=lambda match: match.score, reverse=True)
        return scored[:limit]

    def delete_document(self, document_id: UUID) -> None:
        for chunk_id in [key for key, record in self._records.items() if record.document_id == document_id]:
            del self._records[chunk_id]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match the indexed vectors.")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
