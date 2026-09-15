"""Maintenance jobs: reclaim work whose worker disappeared mid-flight."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_INDEXING,
    TREE_STATUS_BUILDING,
    TREE_STATUS_FAILED,
    Document,
)
from app.models.question import QUESTION_STATUS_FAILED, QUESTION_STATUS_QUEUED, QUESTION_STATUS_RUNNING, Question

STALE_JOB_MESSAGE = (
    "The job was interrupted (worker restart or timeout) and was marked as failed by maintenance."
)
STALE_ERROR_CODE = "stale_job"


@dataclass(frozen=True)
class ReapOutcome:
    documents_failed: int
    questions_failed: int

    @property
    def total(self) -> int:
        return self.documents_failed + self.questions_failed


def reap_stale_jobs(
    session: Session,
    *,
    now: datetime | None = None,
    timeout_seconds: int | None = None,
) -> ReapOutcome:
    """Fail documents and questions that have been in progress for too long."""
    moment = now or datetime.now(UTC)
    timeout = timeout_seconds if timeout_seconds is not None else settings.stale_job_timeout_seconds
    deadline = moment - timedelta(seconds=timeout)

    documents = (
        session.execute(
            select(Document).where(
                Document.updated_at < deadline,
                or_(
                    Document.status == DOCUMENT_STATUS_INDEXING,
                    Document.tree_status == TREE_STATUS_BUILDING,
                ),
            )
        )
        .scalars()
        .all()
    )
    for document in documents:
        if document.status == DOCUMENT_STATUS_INDEXING:
            document.status = DOCUMENT_STATUS_FAILED
            document.error_code = STALE_ERROR_CODE
            document.error_message = STALE_JOB_MESSAGE
        if document.tree_status == TREE_STATUS_BUILDING:
            document.tree_status = TREE_STATUS_FAILED
            document.tree_error = STALE_JOB_MESSAGE

    questions = (
        session.execute(
            select(Question).where(
                Question.created_at < deadline,
                Question.status.in_([QUESTION_STATUS_QUEUED, QUESTION_STATUS_RUNNING]),
            )
        )
        .scalars()
        .all()
    )
    for question in questions:
        question.status = QUESTION_STATUS_FAILED
        question.error_message = STALE_JOB_MESSAGE
        question.answered_at = moment

    session.flush()
    return ReapOutcome(documents_failed=len(documents), questions_failed=len(questions))
