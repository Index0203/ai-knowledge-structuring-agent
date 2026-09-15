"""Stale-job reclamation: stuck work must become a terminal, visible failure."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.models.document import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_INDEXING,
    DOCUMENT_STATUS_UPLOADED,
    TREE_STATUS_BUILDING,
    TREE_STATUS_FAILED,
    TREE_STATUS_READY,
    Document,
)
from app.models.question import (
    QUESTION_STATUS_ANSWERED,
    QUESTION_STATUS_QUEUED,
    QUESTION_STATUS_RUNNING,
    Question,
)
from app.services.maintenance_service import STALE_ERROR_CODE, STALE_JOB_MESSAGE, reap_stale_jobs

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
STALE = NOW - timedelta(hours=2)
FRESH = NOW - timedelta(minutes=5)


def add_document(session, *, status: str, tree_status: str, updated_at: datetime) -> Document:
    document = Document(
        id=uuid4(),
        original_filename="report.pdf",
        media_type="application/pdf",
        storage_key="report.pdf",
        size_bytes=1,
        status=status,
        tree_status=tree_status,
    )
    session.add(document)
    session.flush()
    document.updated_at = updated_at
    session.flush()
    return document


def add_question(session, *, status: str, created_at: datetime) -> Question:
    question = Question(
        id=uuid4(),
        document_id=uuid4(),
        node_id=uuid4(),
        question="这是什么？",
        status=status,
        intent="ask",
    )
    session.add(question)
    session.flush()
    question.created_at = created_at
    session.flush()
    return question


def test_stale_indexing_and_tree_builds_are_failed(session_factory) -> None:
    with session_factory() as session:
        indexing = add_document(session, status=DOCUMENT_STATUS_INDEXING, tree_status="none", updated_at=STALE)
        building = add_document(session, status=DOCUMENT_STATUS_UPLOADED, tree_status=TREE_STATUS_BUILDING, updated_at=STALE)

        outcome = reap_stale_jobs(session, now=NOW)
        session.commit()

        assert outcome.documents_failed == 2
        assert indexing.status == DOCUMENT_STATUS_FAILED
        assert indexing.error_code == STALE_ERROR_CODE
        assert indexing.error_message == STALE_JOB_MESSAGE
        assert building.status == DOCUMENT_STATUS_UPLOADED  # only the tree build was stuck
        assert building.tree_status == TREE_STATUS_FAILED
        assert building.tree_error == STALE_JOB_MESSAGE


def test_fresh_and_finished_work_is_left_alone(session_factory) -> None:
    with session_factory() as session:
        fresh = add_document(session, status=DOCUMENT_STATUS_INDEXING, tree_status="none", updated_at=FRESH)
        ready = add_document(session, status="indexed", tree_status=TREE_STATUS_READY, updated_at=STALE)

        outcome = reap_stale_jobs(session, now=NOW)
        session.commit()

        assert outcome.documents_failed == 0
        assert fresh.status == DOCUMENT_STATUS_INDEXING
        assert ready.tree_status == TREE_STATUS_READY


def test_stale_questions_are_failed_but_answered_ones_are_kept(session_factory) -> None:
    with session_factory() as session:
        queued = add_question(session, status=QUESTION_STATUS_QUEUED, created_at=STALE)
        running = add_question(session, status=QUESTION_STATUS_RUNNING, created_at=STALE)
        answered = add_question(session, status=QUESTION_STATUS_ANSWERED, created_at=STALE)
        recent = add_question(session, status=QUESTION_STATUS_RUNNING, created_at=FRESH)

        outcome = reap_stale_jobs(session, now=NOW)
        session.commit()

        assert outcome.questions_failed == 2
        assert queued.status == "failed"
        assert running.status == "failed"
        assert running.answered_at == NOW
        assert answered.status == QUESTION_STATUS_ANSWERED
        assert recent.status == QUESTION_STATUS_RUNNING


def test_timeout_can_be_overridden_per_call(session_factory) -> None:
    with session_factory() as session:
        document = add_document(
            session,
            status=DOCUMENT_STATUS_INDEXING,
            tree_status="none",
            updated_at=NOW - timedelta(minutes=2),
        )

        assert reap_stale_jobs(session, now=NOW, timeout_seconds=600).documents_failed == 0
        assert reap_stale_jobs(session, now=NOW, timeout_seconds=60).documents_failed == 1
        session.commit()
        assert document.status == DOCUMENT_STATUS_FAILED


def test_reaper_is_idempotent(session_factory) -> None:
    with session_factory() as session:
        add_document(session, status=DOCUMENT_STATUS_INDEXING, tree_status="none", updated_at=STALE)

        first = reap_stale_jobs(session, now=NOW)
        second = reap_stale_jobs(session, now=NOW)
        session.commit()

        assert first.documents_failed == 1
        assert second.documents_failed == 0
