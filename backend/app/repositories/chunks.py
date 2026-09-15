from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.chunk import ContentChunk
from app.pipelines.chunking.contracts import ContentChunkDraft


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_document_chunks(self, document_id: UUID, drafts: list[ContentChunkDraft], embedding_model: str) -> int:
        """Rebuild the chunk set of one document so re-indexing stays idempotent."""
        self._session.execute(delete(ContentChunk).where(ContentChunk.document_id == document_id))
        for draft in drafts:
            self._session.add(
                ContentChunk(
                    id=draft.id,
                    document_id=draft.document_id,
                    section_index=draft.section_index,
                    chunk_index=draft.chunk_index,
                    section_title=draft.section_title,
                    text=draft.text,
                    character_count=len(draft.text),
                    char_start=draft.char_start,
                    char_end=draft.char_end,
                    page_number=draft.page_number,
                    paragraph_index=draft.paragraph_index,
                    embedding_model=embedding_model,
                )
            )
        self._session.flush()
        return len(drafts)

    def list_by_document(self, document_id: UUID) -> list[ContentChunk]:
        return (
            self._session.execute(
                select(ContentChunk)
                .where(ContentChunk.document_id == document_id)
                .order_by(ContentChunk.chunk_index)
            )
            .scalars()
            .all()
        )

    def map_section_indexes_to_chunk_ids(self, document_id: UUID) -> dict[int, list[UUID]]:
        rows = self._session.execute(
            select(ContentChunk.section_index, ContentChunk.id)
            .where(ContentChunk.document_id == document_id)
            .order_by(ContentChunk.chunk_index)
        ).all()
        mapping: dict[int, list[UUID]] = {}
        for section_index, chunk_id in rows:
            mapping.setdefault(section_index, []).append(chunk_id)
        return mapping

    def count_by_document(self, document_id: UUID) -> int:
        return int(
            self._session.execute(
                select(func.count()).select_from(ContentChunk).where(ContentChunk.document_id == document_id)
            ).scalar_one()
        )

    def embedding_model_for_document(self, document_id: UUID) -> str | None:
        return self._session.execute(
            select(ContentChunk.embedding_model)
            .where(ContentChunk.document_id == document_id)
            .limit(1)
        ).scalar_one_or_none()
