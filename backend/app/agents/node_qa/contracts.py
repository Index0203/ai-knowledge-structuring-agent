from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from langchain_core.messages import BaseMessage

from app.schemas.answers import AnswerDraft


@dataclass(frozen=True)
class EvidenceItem:
    """One retrieved content block offered to the answering model."""

    label: str
    chunk_id: UUID
    text: str
    location: str
    section_title: str
    score: float


@dataclass(frozen=True)
class NodeQuizItem:
    """One generated test question with its validated citations."""

    question: str
    answer: str
    cited_chunk_ids: tuple[UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NodeAnswerResult:
    """Validated answer. Refused answers carry no text and no citations."""

    answer: str | None
    cited_chunk_ids: tuple[UUID, ...] = field(default_factory=tuple)
    confidence: float | None = None
    refused: bool = False
    refusal_reason: str | None = None
    quiz_items: tuple[NodeQuizItem, ...] = field(default_factory=tuple)


class AnswerDraftModel(Protocol):
    """A model that returns data conforming to the AnswerDraft schema."""

    def invoke(self, messages: list[BaseMessage]) -> AnswerDraft | dict[str, object]:
        """Generate a grounded answer draft from the provided messages."""
