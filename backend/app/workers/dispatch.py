"""Enqueue helpers used by the HTTP layer so routes never run long work inline."""

from uuid import UUID

from app.workers.tasks import answer_question, build_knowledge_tree, index_document


class TaskDispatchError(RuntimeError):
    """Raised when a background task cannot be queued."""


def dispatch_index_document(document_id: UUID) -> None:
    _dispatch(index_document, document_id, "indexing")


def dispatch_build_knowledge_tree(document_id: UUID) -> None:
    _dispatch(build_knowledge_tree, document_id, "knowledge tree build")


def dispatch_answer_question(question_id: UUID) -> None:
    _dispatch(answer_question, question_id, "question answering")


def _dispatch(task, identifier: UUID, label: str) -> None:
    try:
        task.delay(str(identifier))
    except Exception as error:  # noqa: BLE001 - surfaced as a 503 to the client
        raise TaskDispatchError(f"The {label} task could not be queued.") from error
