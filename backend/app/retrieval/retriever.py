from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings.contracts import EmbeddingProvider
from app.embeddings.factory import create_embedding_provider
from app.models.chunk import ContentChunk
from app.vectorstores.contracts import VectorStore
from app.vectorstores.factory import create_vector_store

SCOPE_NODE_EVIDENCE = "node_evidence"
SCOPE_DOCUMENT = "document"


@dataclass(frozen=True)
class RetrievalResult:
    """A retrieved content block with its score and why it was in scope."""

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    section_index: int
    section_title: str
    text: str
    page_number: int | None
    paragraph_index: int | None
    score: float
    scope: str

    @property
    def location_label(self) -> str:
        if self.page_number is not None:
            return f"p.{self.page_number}"
        if self.paragraph_index is not None:
            return f"¶{self.paragraph_index + 1}"
        return "source"


class Retriever:
    """Document-scoped vector retrieval with node-evidence boosting."""

    def __init__(self, session: Session, embedding_provider: EmbeddingProvider, vector_store: VectorStore) -> None:
        self._session = session
        self._embeddings = embedding_provider
        self._vector_store = vector_store

    def retrieve(
        self,
        *,
        document_id: UUID,
        query: str,
        node_evidence_chunk_ids: frozenset[UUID] = frozenset(),
        top_k: int | None = None,
        min_score: float | None = None,
        node_evidence_boost: float | None = None,
    ) -> list[RetrievalResult]:
        limit = top_k or settings.retrieval_top_k
        threshold = settings.retrieval_min_score if min_score is None else min_score
        boost = settings.node_evidence_boost if node_evidence_boost is None else node_evidence_boost
        if limit <= 0:
            return []

        query_embedding = self._embeddings.embed_query(query)
        candidates = self._vector_store.query(
            document_id=document_id,
            query_embedding=query_embedding,
            limit=max(limit * settings.retrieval_candidate_multiplier, limit),
        )
        if not candidates:
            return []

        chunks = self._load_chunks([candidate.chunk_id for candidate in candidates])
        results: list[RetrievalResult] = []
        for candidate in candidates:
            if candidate.score < threshold:
                continue
            chunk = chunks.get(candidate.chunk_id)
            if chunk is None:
                # The vector index drifted from PostgreSQL; PostgreSQL wins.
                continue
            in_node_scope = candidate.chunk_id in node_evidence_chunk_ids
            results.append(
                RetrievalResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    section_index=chunk.section_index,
                    section_title=chunk.section_title,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    paragraph_index=chunk.paragraph_index,
                    score=round(candidate.score + (boost if in_node_scope else 0.0), 6),
                    scope=SCOPE_NODE_EVIDENCE if in_node_scope else SCOPE_DOCUMENT,
                )
            )

        results.sort(key=lambda result: (-result.score, result.chunk_index))
        return results[:limit]

    def _load_chunks(self, chunk_ids: list[UUID]) -> dict[UUID, ContentChunk]:
        if not chunk_ids:
            return {}
        rows = self._session.execute(select(ContentChunk).where(ContentChunk.id.in_(chunk_ids))).scalars().all()
        return {row.id: row for row in rows}


def create_retriever(session: Session) -> Retriever:
    return Retriever(session, create_embedding_provider(), create_vector_store())
