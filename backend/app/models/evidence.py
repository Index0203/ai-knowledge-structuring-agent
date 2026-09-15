from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.document import utc_now

EVIDENCE_TARGET_NODE = "knowledge_node"
EVIDENCE_TARGET_EDGE = "knowledge_edge"
EVIDENCE_TARGET_ANSWER = "answer"


class EvidenceLink(Base):
    """The single evidence bridge between a content block and a generated artifact."""

    __tablename__ = "evidence_links"
    __table_args__ = (Index("ix_evidence_links_target", "target_type", "target_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("content_chunks.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID] = mapped_column()
    source_section_index: Mapped[int | None] = mapped_column(Integer, default=None)
    rank: Mapped[int | None] = mapped_column(Integer, default=None)
    relevance: Mapped[float | None] = mapped_column(Float, default=None)
    quote: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
