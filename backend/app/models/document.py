from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DOCUMENT_STATUS_UPLOADED = "uploaded"
DOCUMENT_STATUS_INDEXING = "indexing"
DOCUMENT_STATUS_INDEXED = "indexed"
DOCUMENT_STATUS_FAILED = "failed"

TREE_STATUS_NONE = "none"
TREE_STATUS_BUILDING = "building"
TREE_STATUS_READY = "ready"
TREE_STATUS_FAILED = "failed"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Document(Base):
    """An uploaded source document plus the state of its derived artifacts."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=DOCUMENT_STATUS_UPLOADED)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    error_code: Mapped[str | None] = mapped_column(String(48), default=None)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    paragraph_count: Mapped[int | None] = mapped_column(Integer, default=None)
    ocr_page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    tree_status: Mapped[str] = mapped_column(String(32), default=TREE_STATUS_NONE)
    tree_error: Mapped[str | None] = mapped_column(Text, default=None)
    tree_mode: Mapped[str | None] = mapped_column(String(32), default=None)
    tree_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    map_model: Mapped[dict[str, object] | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
