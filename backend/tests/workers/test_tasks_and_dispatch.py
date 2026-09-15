"""Worker layer: task bodies and the enqueue helpers the HTTP layer depends on."""

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest

from app.workers import dispatch as dispatch_module
from app.workers.dispatch import (
    TaskDispatchError,
    dispatch_answer_question,
    dispatch_build_knowledge_tree,
    dispatch_index_document,
)
from app.workers.tasks import answer_question, build_knowledge_tree, index_document

DOCUMENT_ID = uuid4()
QUESTION_ID = uuid4()


class FakeTask:
    def __init__(self) -> None:
        self.delayed: list[str] = []
        self.error: Exception | None = None

    def delay(self, identifier: str) -> None:
        if self.error is not None:
            raise self.error
        self.delayed.append(identifier)


class StubOutcome:
    def __init__(self, **fields) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


def session_scope_stub(session):
    @contextmanager
    def scope():
        yield session

    return scope


def test_dispatch_helpers_enqueue_string_identifiers(monkeypatch) -> None:
    task = FakeTask()
    monkeypatch.setattr(dispatch_module, "index_document", task)
    monkeypatch.setattr(dispatch_module, "build_knowledge_tree", task)
    monkeypatch.setattr(dispatch_module, "answer_question", task)

    dispatch_index_document(DOCUMENT_ID)
    dispatch_build_knowledge_tree(DOCUMENT_ID)
    dispatch_answer_question(QUESTION_ID)

    assert task.delayed == [str(DOCUMENT_ID), str(DOCUMENT_ID), str(QUESTION_ID)]


def test_dispatch_helpers_wrap_queue_failures(monkeypatch) -> None:
    task = FakeTask()
    task.error = RuntimeError("redis down")
    monkeypatch.setattr(dispatch_module, "index_document", task)

    with pytest.raises(TaskDispatchError, match="indexing task could not be queued"):
        dispatch_index_document(DOCUMENT_ID)


def test_index_document_task_returns_a_summary(monkeypatch) -> None:
    outcome = StubOutcome(
        document_id=DOCUMENT_ID,
        status="indexed",
        chunk_count=4,
        embedding_model="deterministic-hashing-256",
        error_message=None,
    )

    class StubService:
        def index(self, document_id):
            assert isinstance(document_id, UUID)
            return outcome

    monkeypatch.setattr("app.workers.tasks.session_scope", lambda: session_scope_stub(object)())
    monkeypatch.setattr("app.workers.tasks.create_document_indexing_service", lambda _session: StubService())

    result = index_document(str(DOCUMENT_ID))

    assert result == {
        "document_id": str(DOCUMENT_ID),
        "status": "indexed",
        "chunk_count": 4,
        "embedding_model": "deterministic-hashing-256",
        "error_message": None,
        "attempt": 0,
    }


def test_build_knowledge_tree_task_returns_a_summary(monkeypatch) -> None:
    outcome = StubOutcome(
        document_id=DOCUMENT_ID,
        status="ready",
        mode="llm",
        node_count=12,
        error_message=None,
    )

    class StubService:
        def __init__(self, _session) -> None:
            pass

        def build(self, document_id):
            assert isinstance(document_id, UUID)
            return outcome

    monkeypatch.setattr("app.workers.tasks.session_scope", lambda: session_scope_stub(object)())
    monkeypatch.setattr("app.workers.tasks.KnowledgeTreeService", StubService)

    result = build_knowledge_tree(str(DOCUMENT_ID))

    assert result["status"] == "ready"
    assert result["mode"] == "llm"
    assert result["node_count"] == 12


def test_answer_question_task_returns_a_summary(monkeypatch) -> None:
    outcome = StubOutcome(
        question_id=QUESTION_ID,
        status="answered",
        answer_mode="llm",
        citation_count=3,
        refused=False,
    )

    class StubService:
        def __init__(self, _session) -> None:
            pass

        def answer(self, question_id):
            assert isinstance(question_id, UUID)
            return outcome

    monkeypatch.setattr("app.workers.tasks.session_scope", lambda: session_scope_stub(object)())
    monkeypatch.setattr("app.workers.tasks.QuestionService", StubService)

    result = answer_question(str(QUESTION_ID))

    assert result == {
        "question_id": str(QUESTION_ID),
        "status": "answered",
        "answer_mode": "llm",
        "citation_count": 3,
        "refused": False,
        "attempt": 0,
    }
