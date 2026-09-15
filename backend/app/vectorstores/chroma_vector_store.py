from uuid import UUID

import chromadb

from app.core.config import settings
from app.vectorstores.contracts import VectorMatch, VectorRecord


class ChromaVectorStore:
    """ChromaDB adapter. Only ids, vectors and filter metadata live here."""

    def __init__(self, host: str, port: int, collection_name: str) -> None:
        self._client = chromadb.HttpClient(host=host, port=port)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        self._collection.upsert(
            ids=[str(record.chunk_id) for record in records],
            embeddings=[record.embedding for record in records],
            metadatas=[record.metadata for record in records],
            documents=[record.text for record in records],
        )

    def query(self, *, document_id: UUID, query_embedding: list[float], limit: int) -> list[VectorMatch]:
        if limit <= 0:
            return []
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"document_id": str(document_id)},
            include=["distances"],
        )
        ids = result.get("ids") or [[]]
        distances = result.get("distances") or [[]]
        return [
            VectorMatch(chunk_id=UUID(chunk_id), score=1.0 - float(distance))
            for chunk_id, distance in zip(ids[0], distances[0], strict=False)
        ]

    def delete_document(self, document_id: UUID) -> None:
        self._collection.delete(where={"document_id": str(document_id)})


def create_chroma_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=settings.chroma_collection,
    )
