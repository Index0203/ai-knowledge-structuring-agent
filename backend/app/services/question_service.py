"""Creates node questions and persists tutor answers produced by the agent workflow."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.node_qa.prompts import PROMPT_VERSION
from app.agents.workflow.graph import run_workflow
from app.agents.workflow.state import (
    TaskType,
    TutorReply,
    WorkflowDependencies,
    WorkflowRequest,
    WorkflowStatus,
)
from app.core.config import settings
from app.models.chunk import ContentChunk
from app.models.evidence import EVIDENCE_TARGET_ANSWER
from app.models.question import (
    ANSWER_MODE_EXTRACTIVE,
    INTENT_ASK,
    QUESTION_STATUS_ANSWERED,
    QUESTION_STATUS_INSUFFICIENT,
    QUESTION_STATUS_QUEUED,
    Question,
)
from app.repositories.documents import DocumentRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.questions import QuestionRepository
from app.retrieval.retriever import Retriever
from app.agents.node_qa.agent import NodeQuestionAgent
from app.workers.retry_policy import is_transient_error
from app.schemas.answers import AnswerCitationResponse, QuestionAnswerResponse, QuizItemResponse


@dataclass(frozen=True)
class AnswerOutcome:
    question_id: UUID
    status: str
    answer_mode: str | None
    citation_count: int
    refused: bool
    quiz_item_count: int = 0


class QuestionService:
    """Thin persistence layer around the Tutor Agent."""

    def __init__(
        self,
        session: Session,
        *,
        retriever: Retriever | None = None,
        answer_agent: NodeQuestionAgent | None = None,
        dispatch: Callable[[UUID], None] | None = None,
        dispatcher: Callable[[UUID], None] | None = None,
    ) -> None:
        self._session = session
        self._retriever = retriever
        self._answer_agent = answer_agent
        self._dispatcher = dispatcher or dispatch

    def submit(self, *, node_id: UUID, question_text: str, intent: str = INTENT_ASK) -> Question:
        node = KnowledgeRepository(self._session).get_node(node_id)
        if node is None:
            raise LookupError(f"Knowledge node {node_id} does not exist.")

        question = QuestionRepository(self._session).create(
            document_id=node.document_id,
            node_id=node.id,
            question_text=question_text,
            intent=intent,
        )
        question.status = QUESTION_STATUS_QUEUED
        question.prompt_version = PROMPT_VERSION
        self._session.commit()
        try:
            self._dispatch(question.id)
        except Exception as error:  # noqa: BLE001 - keep the question state truthful
            question.status = "failed"
            question.error_message = str(error)
            self._session.commit()
            raise
        return question

    def answer(self, question_id: UUID) -> AnswerOutcome:
        questions = QuestionRepository(self._session)
        question = questions.get(question_id)
        if question is None:
            raise LookupError(f"Question {question_id} does not exist.")

        started_at = time.perf_counter()
        questions.mark_running(question)
        self._session.flush()

        try:
            reply = self._teach(question)
        except Exception as error:  # noqa: BLE001 - classify before deciding the terminal state
            if is_transient_error(error):
                # Let Celery retry with backoff; the row stays running and is either
                # finished on a later attempt or failed by the task / reaper.
                raise
            questions.mark_failed(question, f"The assistant could not produce an answer: {error}")
            return AnswerOutcome(question.id, question.status, None, 0, True)

        payload = _quiz_payload(reply)
        citation_ids = [citation.chunk_id for citation in reply.citations]
        quiz_citation_ids = [
            citation.chunk_id for item in reply.quiz_items for citation in item.citations
        ]
        all_citation_ids = citation_ids + [chunk_id for chunk_id in quiz_citation_ids if chunk_id not in citation_ids]

        if reply.refused:
            questions.mark_answered(
                question,
                status=QUESTION_STATUS_INSUFFICIENT,
                answer=None,
                answer_mode=reply.mode if reply.mode == ANSWER_MODE_EXTRACTIVE else None,
                model=settings.openai_model if reply.mode != ANSWER_MODE_EXTRACTIVE else None,
                prompt_version=PROMPT_VERSION,
                confidence=reply.confidence,
                refusal_reason=reply.refusal_reason or "The answer could not be traced to retrieved evidence.",
                latency_ms=_elapsed_ms(started_at),
                answer_payload=payload or None,
            )
            return AnswerOutcome(question.id, question.status, reply.mode, 0, True, len(reply.quiz_items))

        questions.mark_answered(
            question,
            status=QUESTION_STATUS_ANSWERED,
            answer=reply.answer,
            answer_mode=reply.mode,
            model=settings.openai_model if reply.mode != ANSWER_MODE_EXTRACTIVE else None,
            prompt_version=PROMPT_VERSION,
            confidence=reply.confidence,
            refusal_reason=None,
            latency_ms=_elapsed_ms(started_at),
            answer_payload=payload or None,
        )
        if all_citation_ids:
            EvidenceRepository(self._session).add_links(
                document_id=question.document_id,
                target_type=EVIDENCE_TARGET_ANSWER,
                target_id=question.id,
                chunk_ids=all_citation_ids,
                relevance=reply.citations[0].relevance if reply.citations else None,
            )
        self._session.flush()
        return AnswerOutcome(
            question.id,
            question.status,
            reply.mode,
            len(all_citation_ids),
            False,
            len(reply.quiz_items),
        )

    def _teach(self, question: Question) -> TutorReply:
        """Run the Tutor Agent through the multi-agent workflow."""
        deps = WorkflowDependencies(
            session=self._session,
            upload_dir=settings.upload_dir,
            retriever=self._retriever,
            answer_agent_factory=None,
            metadata={"answer_agent": self._answer_agent},
        )
        state = run_workflow(
            deps=deps,
            request=WorkflowRequest(
                task_type=TaskType.TEACH_NODE,
                document_id=question.document_id,
                node_id=question.node_id,
                node_intent=question.intent or INTENT_ASK,
                question=question.question,
            ),
        )
        reply = state.get("tutor")
        if state.get("status") == WorkflowStatus.FAILED or reply is None:
            raise RuntimeError("; ".join(state.get("errors", [])) or "the tutor workflow failed")
        return reply

    def _dispatch(self, question_id: UUID) -> None:
        if self._dispatcher is not None:
            self._dispatcher(question_id)
            return
        from app.workers.dispatch import dispatch_answer_question

        dispatch_answer_question(question_id)


def _quiz_payload(reply: TutorReply) -> list[dict[str, object]]:
    return [
        {
            "question": item.question,
            "answer": item.answer,
            "citations": [
                {
                    "chunk_id": str(citation.chunk_id),
                    "quote": citation.quote,
                    "section_title": citation.section_title,
                    "location": citation.location,
                    "relevance": citation.relevance,
                }
                for citation in item.citations
            ],
        }
        for item in reply.quiz_items
    ]


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


class QuestionNotFoundError(Exception):
    """Raised when a question id has no persisted question."""


def load_question_answer(session: Session, question_id: UUID) -> QuestionAnswerResponse:
    question = QuestionRepository(session).get(question_id)
    if question is None:
        raise QuestionNotFoundError(f"Question {question_id} does not exist.")

    links = EvidenceRepository(session).citations_for_target(EVIDENCE_TARGET_ANSWER, question.id)
    chunks = {chunk.id: chunk for _link, chunk in links}
    citations = [
        _citation_response(chunk, link.relevance if link.relevance is not None else 0.0, link.quote)
        for link, chunk in links
    ]
    quiz_items = [
        QuizItemResponse(
            question=str(item.get("question", "")),
            answer=str(item.get("answer", "")),
            citations=[_payload_citation(citation, chunks) for citation in item.get("citations", [])],
        )
        for item in (question.answer_payload or [])
    ]
    return QuestionAnswerResponse(
        question_id=question.id,
        document_id=question.document_id,
        node_id=question.node_id,
        intent=question.intent or INTENT_ASK,
        question=question.question,
        status=question.status,
        answer=question.answer,
        answer_mode=question.answer_mode,
        model=question.model,
        prompt_version=question.prompt_version,
        confidence=question.confidence,
        citations=citations,
        quiz_items=quiz_items,
        error_message=question.error_message or question.refusal_reason,
        latency_ms=question.latency_ms,
        created_at=question.created_at,
        answered_at=question.answered_at,
    )


def _citation_response(chunk: ContentChunk, relevance: float, quote: str | None) -> AnswerCitationResponse:
    return AnswerCitationResponse(
        chunk_id=chunk.id,
        quote=quote or chunk.text,
        section_title=chunk.section_title,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        paragraph_index=chunk.paragraph_index,
        relevance=relevance,
    )


def _payload_citation(citation: dict[str, object], chunks: dict[UUID, ContentChunk]) -> AnswerCitationResponse:
    """Prefer the stored chunk; fall back to the snapshot kept in the payload."""
    chunk_id_value = str(citation.get("chunk_id", ""))
    try:
        chunk_id = UUID(chunk_id_value)
    except ValueError:
        chunk_id = None
    chunk = chunks.get(chunk_id) if chunk_id else None
    if chunk is not None:
        return _citation_response(chunk, float(citation.get("relevance") or 0.0), str(citation.get("quote") or ""))
    return AnswerCitationResponse(
        chunk_id=chunk_id or UUID(int=0),
        quote=str(citation.get("quote") or ""),
        section_title=str(citation.get("section_title") or ""),
        chunk_index=0,
        page_number=None,
        paragraph_index=None,
        relevance=float(citation.get("relevance") or 0.0),
    )
