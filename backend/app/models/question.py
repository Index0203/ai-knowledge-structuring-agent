from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.document import utc_now

QUESTION_STATUS_QUEUED = "queued"
QUESTION_STATUS_RUNNING = "running"
QUESTION_STATUS_ANSWERED = "answered"
QUESTION_STATUS_INSUFFICIENT = "insufficient_evidence"
QUESTION_STATUS_FAILED = "failed"

ANSWER_MODE_LLM = "llm"
ANSWER_MODE_EXTRACTIVE = "extractive_fallback"
INTENT_ASK = "ask"


class Question(Base):
    """A user question about one knowledge node and the grounded answer, if any."""

    __tablename__ = "questions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(32), default=INTENT_ASK, server_default=INTENT_ASK)
    status: Mapped[str] = mapped_column(String(32), default=QUESTION_STATUS_QUEUED)
    answer: Mapped[str | None] = mapped_column(Text, default=None)
    answer_mode: Mapped[str | None] = mapped_column(String(32), default=None)
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    prompt_version: Mapped[str | None] = mapped_column(String(64), default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    refusal_reason: Mapped[str | None] = mapped_column(Text, default=None)
    answer_payload: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
