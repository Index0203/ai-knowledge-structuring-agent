"""Time limits, retry policy and terminal-state guarantees for background work."""

from uuid import uuid4

import httpx
import pytest

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.retry_policy import is_transient_error, transient_exceptions
from app.workers.tasks import answer_question, build_knowledge_tree, index_document


def test_long_running_tasks_have_time_limits() -> None:
    assert index_document.soft_time_limit > 0
    assert index_document.time_limit > index_document.soft_time_limit
    assert build_knowledge_tree.time_limit > build_knowledge_tree.soft_time_limit
    # Answering is a single model call, so it must fail fast instead of blocking a worker.
    assert answer_question.time_limit <= 300
    assert answer_question.time_limit < index_document.time_limit


def test_worker_configuration_avoids_losing_tasks() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.task_default_retry_delay == settings.task_retry_backoff_seconds


def test_transient_failures_are_retried_with_backoff() -> None:
    annotation = celery_app.conf.task_annotations["*"]

    assert annotation["retry_backoff"] is True
    assert annotation["retry_jitter"] is True
    assert annotation["max_retries"] == settings.task_max_retries
    assert TimeoutError in annotation["autoretry_for"]
    assert ConnectionError in annotation["autoretry_for"]


def test_reaper_is_scheduled() -> None:
    schedule = celery_app.conf.beat_schedule

    assert "reap-stale-jobs" in schedule
    assert schedule["reap-stale-jobs"]["task"] == "maintenance.reap_stale_jobs"
    assert schedule["reap-stale-jobs"]["schedule"] == float(settings.reaper_interval_seconds)
    # The scheduler database must not land in the bind-mounted source tree.
    assert celery_app.conf.beat_schedule_filename.startswith("/tmp/")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (TimeoutError("slow"), True),
        (ConnectionError("reset"), True),
        (httpx.ConnectError("no route"), True),
        (httpx.ReadTimeout("slow"), True),
        (ValueError("schema invalid"), False),
        (RuntimeError("provider exploded"), False),
    ],
)
def test_transient_classification(error: Exception, expected: bool) -> None:
    assert is_transient_error(error) is expected


def test_transient_types_are_exception_classes() -> None:
    for candidate in transient_exceptions():
        assert isinstance(candidate, type) and issubclass(candidate, BaseException)


def test_final_attempt_is_detected() -> None:
    from app.workers.tasks import is_final_attempt

    class FakeRequest:
        def __init__(self, retries: int) -> None:
            self.retries = retries

    class FakeTask:
        max_retries = 2

        def __init__(self, retries: int) -> None:
            self.request = FakeRequest(retries)

    assert is_final_attempt(FakeTask(0)) is False
    assert is_final_attempt(FakeTask(1)) is False
    assert is_final_attempt(FakeTask(2)) is True
    assert is_final_attempt(FakeTask(3)) is True


def test_question_failure_helper_leaves_terminal_states_alone(session_factory) -> None:
    from app.models.question import QUESTION_STATUS_ANSWERED, QUESTION_STATUS_RUNNING
    from app.models.question import Question
    from app.repositories.questions import QuestionRepository
    from app.workers.tasks import _mark_question_failed

    running_id = uuid4()
    answered_id = uuid4()
    with session_factory() as session:
        for identifier, status in ((running_id, QUESTION_STATUS_RUNNING), (answered_id, QUESTION_STATUS_ANSWERED)):
            session.add(
                Question(
                    id=identifier,
                    document_id=uuid4(),
                    node_id=uuid4(),
                    question="?",
                    status=status,
                    intent="ask",
                )
            )
        session.commit()

    from app import db

    import app.workers.tasks as tasks_module

    original = db.session.SessionLocal
    try:
        db.session.SessionLocal = session_factory  # type: ignore[assignment]
        tasks_module._mark_question_failed(str(running_id), "provider timed out")
        tasks_module._mark_question_failed(str(answered_id), "must not overwrite")
    finally:
        db.session.SessionLocal = original  # type: ignore[assignment]

    with session_factory() as session:
        assert QuestionRepository(session).get(running_id).status == "failed"
        assert QuestionRepository(session).get(running_id).error_message == "provider timed out"
        assert QuestionRepository(session).get(answered_id).status == QUESTION_STATUS_ANSWERED
