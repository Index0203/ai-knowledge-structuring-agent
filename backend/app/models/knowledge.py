from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.document import utc_now


class KnowledgeNode(Base):
    """A persisted knowledge node with a stable id used by node-scoped questions."""

    __tablename__ = "knowledge_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), default=None, index=True
    )
    path: Mapped[str] = mapped_column(String(64))
    depth: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeEdge(Base):
    """A persisted parent-child relation between two knowledge nodes."""

    __tablename__ = "knowledge_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    parent_node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True)
    child_node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(32), default="contains")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
