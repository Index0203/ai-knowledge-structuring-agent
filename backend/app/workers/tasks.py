"""Celery tasks. Every long-running parse, embedding or model call happens here.

Reliability rules:
- each task has a soft/hard time limit sized to the work it does;
- transient failures are retried with backoff (see `retry_policy`);
- after the final attempt the owning row is marked failed, so the UI stops polling
  instead of waiting for the maintenance reaper.
"""

from uuid import UUID

from celery import Task

from app.db.session import session_scope
from app.services.indexing_service import create_document_indexing_service
from app.services.knowledge_tree_service import KnowledgeTreeService
from app.services.maintenance_service import reap_stale_jobs
from app.services.question_service import QuestionService
from app.workers.celery_app import celery_app

INDEXING_SOFT_LIMIT = 1800
INDEXING_HARD_LIMIT = 2100
ANSWER_SOFT_LIMIT = 120
ANSWER_HARD_LIMIT = 180
REAPER_SOFT_LIMIT = 60
REAPER_HARD_LIMIT = 120


def is_final_attempt(task: Task) -> bool:
    """True when Celery will not retry this task again."""
    retries = getattr(task.request, "retries", 0) or 0
    return retries >= (task.max_retries or 0)


def _mark_question_failed(question_id: str, message: str) -> None:
    from app.repositories.questions import QuestionRepository

    with session_scope() as session:
        question = QuestionRepository(session).get(UUID(question_id))
        if question is not None and question.status not in {"answered", "insufficient_evidence", "failed"}:
            QuestionRepository(session).mark_failed(question, message)


@celery_app.task(
    bind=True,
    name="documents.index",
    soft_time_limit=INDEXING_SOFT_LIMIT,
    time_limit=INDEXING_HARD_LIMIT,
)
def index_document(self, document_id: str) -> dict[str, object]:
    with session_scope() as session:
        outcome = create_document_indexing_service(session).index(UUID(document_id))
        return {
            "document_id": str(outcome.document_id),
            "status": outcome.status,
            "chunk_count": outcome.chunk_count,
            "embedding_model": outcome.embedding_model,
            "error_message": outcome.error_message,
            "attempt": self.request.retries,
        }


@celery_app.task(
    bind=True,
    name="documents.build_knowledge_tree",
    soft_time_limit=INDEXING_SOFT_LIMIT,
    time_limit=INDEXING_HARD_LIMIT,
)
def build_knowledge_tree(self, document_id: str) -> dict[str, object]:
    with session_scope() as session:
        outcome = KnowledgeTreeService(session).build(UUID(document_id))
        return {
            "document_id": str(outcome.document_id),
            "status": outcome.status,
            "mode": outcome.mode,
            "node_count": outcome.node_count,
            "error_message": outcome.error_message,
            "attempt": self.request.retries,
        }


@celery_app.task(
    bind=True,
    name="questions.answer",
    soft_time_limit=ANSWER_SOFT_LIMIT,
    time_limit=ANSWER_HARD_LIMIT,
)
def answer_question(self, question_id: str) -> dict[str, object]:
    try:
        with session_scope() as session:
            outcome = QuestionService(session).answer(UUID(question_id))
            return {
                "question_id": str(outcome.question_id),
                "status": outcome.status,
                "answer_mode": outcome.answer_mode,
                "citation_count": outcome.citation_count,
                "refused": outcome.refused,
                "attempt": self.request.retries,
            }
    except Exception as error:  # noqa: BLE001 - the last attempt must leave a terminal state
        if is_final_attempt(self):
            _mark_question_failed(question_id, f"The assistant could not produce an answer: {error}")
        raise


@celery_app.task(
    name="maintenance.reap_stale_jobs",
    soft_time_limit=REAPER_SOFT_LIMIT,
    time_limit=REAPER_HARD_LIMIT,
)
def reap_stale_jobs_task() -> dict[str, int]:
    """Fail jobs whose worker disappeared, so the UI stops polling them."""
    with session_scope() as session:
        outcome = reap_stale_jobs(session)
        return {
            "documents_failed": outcome.documents_failed,
            "questions_failed": outcome.questions_failed,
        }


__all__ = [
    "answer_question",
    "build_knowledge_tree",
    "index_document",
    "reap_stale_jobs_task",
]
