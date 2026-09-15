from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_ANSWER_CHARACTERS = 6000
MAX_QUIZ_ANSWER_CHARACTERS = 1500
MAX_QUIZ_QUESTION_CHARACTERS = 400


def _truncate(value: object, limit: int) -> object:
    """Model output is trimmed rather than rejected: a verbose answer is still an answer."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit]
    return value


class AnswerDraft(BaseModel):
    """Structured output the answering model must produce."""

    # Model output: required fields are validated, unknown fields are ignored.
    model_config = ConfigDict(extra="ignore")

    answer: str = Field(min_length=1, max_length=MAX_ANSWER_CHARACTERS)
    cited_evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    insufficient_evidence: bool = False
    quiz_items: list["QuizItemDraft"] = Field(default_factory=list, max_length=8)

    @field_validator("answer", mode="before")
    @classmethod
    def _trim_answer(cls, value: object) -> object:
        return _truncate(value, MAX_ANSWER_CHARACTERS)


class QuizItemDraft(BaseModel):
    """One generated test question with its reference answer."""

    model_config = ConfigDict(extra="ignore")

    question: str = Field(min_length=1, max_length=MAX_QUIZ_QUESTION_CHARACTERS)
    answer: str = Field(min_length=1, max_length=MAX_QUIZ_ANSWER_CHARACTERS)
    cited_evidence_ids: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("question", mode="before")
    @classmethod
    def _trim_question(cls, value: object) -> object:
        return _truncate(value, MAX_QUIZ_QUESTION_CHARACTERS)

    @field_validator("answer", mode="before")
    @classmethod
    def _trim_quiz_answer(cls, value: object) -> object:
        return _truncate(value, MAX_QUIZ_ANSWER_CHARACTERS)


class AnswerCitationResponse(BaseModel):
    chunk_id: UUID
    quote: str
    section_title: str
    chunk_index: int
    page_number: int | None
    paragraph_index: int | None
    relevance: float


class QuizItemResponse(BaseModel):
    question: str
    answer: str
    citations: list[AnswerCitationResponse] = Field(default_factory=list)


class QuestionSubmittedResponse(BaseModel):
    question_id: UUID
    node_id: UUID
    intent: str
    status: str
    created_at: datetime


class QuestionAnswerResponse(BaseModel):
    question_id: UUID
    document_id: UUID
    node_id: UUID
    intent: str
    question: str
    status: str
    answer: str | None
    answer_mode: str | None
    model: str | None
    prompt_version: str | None
    confidence: float | None
    citations: list[AnswerCitationResponse] = Field(default_factory=list)
    quiz_items: list[QuizItemResponse] = Field(default_factory=list)
    error_message: str | None
    latency_ms: int | None
    created_at: datetime
    answered_at: datetime | None
