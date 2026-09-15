from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.question import Question


class QuestionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, *, document_id: UUID, node_id: UUID, question_text: str, intent: str = "ask") -> Question:
        question = Question(
            id=uuid4(),
            document_id=document_id,
            node_id=node_id,
            question=question_text,
            intent=intent,
        )
        self._session.add(question)
        self._session.flush()
        return question

    def get(self, question_id: UUID) -> Question | None:
        return self._session.get(Question, question_id)

    def list_for_node(self, node_id: UUID, limit: int = 20) -> list[Question]:
        return (
            self._session.execute(
                select(Question)
                .where(Question.node_id == node_id)
                .order_by(Question.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def mark_running(question: Question) -> None:
        question.status = "running"

    def mark_answered(
        self,
        question: Question,
        *,
        status: str,
        answer: str | None,
        answer_mode: str | None,
        model: str | None,
        prompt_version: str | None,
        confidence: float | None,
        refusal_reason: str | None,
        latency_ms: int,
        answer_payload: list[dict[str, object]] | None = None,
    ) -> None:
        question.status = status
        question.answer = answer
        question.answer_mode = answer_mode
        question.model = model
        question.prompt_version = prompt_version
        question.confidence = confidence
        question.refusal_reason = refusal_reason
        question.answer_payload = answer_payload
        question.latency_ms = latency_ms
        question.answered_at = datetime.now(UTC)
        self._session.flush()

    def mark_failed(self, question: Question, message: str) -> None:
        question.status = "failed"
        question.error_message = message
        question.answered_at = datetime.now(UTC)
        self._session.flush()
