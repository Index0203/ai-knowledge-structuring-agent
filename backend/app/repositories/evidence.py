from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chunk import ContentChunk
from app.models.evidence import EvidenceLink

MAX_QUOTE_CHARACTERS = 240


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_links(
        self,
        *,
        document_id: UUID,
        target_type: str,
        target_id: UUID,
        chunk_ids: list[UUID],
        source_section_index: int | None = None,
        relevance: float | None = None,
    ) -> list[EvidenceLink]:
        links: list[EvidenceLink] = []
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            link = EvidenceLink(
                id=uuid4(),
                document_id=document_id,
                chunk_id=chunk_id,
                target_type=target_type,
                target_id=target_id,
                source_section_index=source_section_index,
                rank=rank,
                relevance=relevance,
            )
            self._session.add(link)
            links.append(link)
        self._session.flush()
        return links

    def delete_for_targets(self, document_id: UUID, target_type: str) -> None:
        self._session.execute(
            delete(EvidenceLink).where(
                EvidenceLink.document_id == document_id,
                EvidenceLink.target_type == target_type,
            )
        )

    def chunk_ids_for_target(self, target_type: str, target_id: UUID) -> list[UUID]:
        rows = self._session.execute(
            select(EvidenceLink.chunk_id)
            .where(EvidenceLink.target_type == target_type, EvidenceLink.target_id == target_id)
            .order_by(EvidenceLink.rank)
        ).all()
        return [row[0] for row in rows]

    def citations_for_target(self, target_type: str, target_id: UUID) -> list[tuple[EvidenceLink, ContentChunk]]:
        return (
            self._session.execute(
                select(EvidenceLink, ContentChunk)
                .join(ContentChunk, ContentChunk.id == EvidenceLink.chunk_id)
                .where(EvidenceLink.target_type == target_type, EvidenceLink.target_id == target_id)
                .order_by(EvidenceLink.rank)
            )
            .all()
        )
