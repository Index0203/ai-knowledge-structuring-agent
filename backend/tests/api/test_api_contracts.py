"""API contract tests: status codes, error semantics and response shape."""

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.workers.dispatch import TaskDispatchError
from tests.helpers import prepare_indexed_document


def test_processing_returns_503_when_the_queue_is_unavailable(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    upload = client.post(
        "/api/v1/uploads",
        files={"file": ("notes.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )
    document_id = upload.json()["document_id"]

    def exploding_dispatch(_document_id):
        raise TaskDispatchError("Redis is unreachable.")

    monkeypatch.setattr("app.api.routes.documents.dispatch_index_document", exploding_dispatch)
    response = client.post(f"/api/v1/documents/{document_id}/processing")

    assert response.status_code == 503
    assert "Redis is unreachable" in response.json()["detail"]
    # The document must not claim to be processing when nothing was queued.
    assert client.get(f"/api/v1/documents/{document_id}").json()["status"] == "failed"


def test_tree_trigger_returns_503_when_the_queue_is_unavailable(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    upload = client.post(
        "/api/v1/uploads",
        files={"file": ("notes.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )
    document_id = upload.json()["document_id"]

    def exploding_dispatch(_document_id):
        raise TaskDispatchError("Redis is unreachable.")

    monkeypatch.setattr("app.api.routes.documents.dispatch_build_knowledge_tree", exploding_dispatch)
    response = client.post(f"/api/v1/documents/{document_id}/knowledge-tree")

    assert response.status_code == 503
    assert client.get(f"/api/v1/documents/{document_id}").json()["tree_status"] == "failed"


def test_processing_an_unknown_document_returns_404(client) -> None:
    assert client.post(f"/api/v1/documents/{uuid4()}/processing").status_code == 404


def test_unknown_document_and_tree_lookups_return_404(client) -> None:
    unknown = uuid4()

    assert client.get(f"/api/v1/documents/{unknown}").status_code == 404
    assert client.get(f"/api/v1/documents/{unknown}/knowledge-tree").status_code == 404
    assert client.get(f"/api/v1/questions/{unknown}").status_code == 404


def test_question_requires_text_unless_an_intent_is_given(client, session_factory, vector_store, embedding_provider, tmp_path, monkeypatch) -> None:
    document_id = prepare_indexed_document(
        client=client,
        session_factory=session_factory,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    node_id = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()["tree"]["children"][0]["id"]

    empty = client.post(f"/api/v1/knowledge-nodes/{node_id}/questions", json={"intent": "ask", "question": " "})
    with_intent = client.post(f"/api/v1/knowledge-nodes/{node_id}/questions", json={"intent": "explain"})

    assert empty.status_code == 422
    assert with_intent.status_code == 202
    assert with_intent.json()["intent"] == "explain"


def test_unknown_intent_value_is_treated_as_a_free_form_question(
    client, session_factory, vector_store, embedding_provider, tmp_path, monkeypatch
) -> None:
    document_id = prepare_indexed_document(
        client=client,
        session_factory=session_factory,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    node_id = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()["tree"]["children"][0]["id"]

    response = client.post(
        f"/api/v1/knowledge-nodes/{node_id}/questions",
        json={"intent": "summarise-everything", "question": "这是什么？"},
    )

    assert response.status_code == 202
    assert response.json()["intent"] == "ask"


def test_empty_upload_is_rejected(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    response = client.post(
        "/api/v1/uploads",
        files={"file": ("empty.pdf", BytesIO(b"").read(), "application/pdf")},
    )

    assert response.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_answer_response_exposes_traceability_fields(
    client, session_factory, vector_store, embedding_provider, tmp_path, monkeypatch
) -> None:
    document_id = prepare_indexed_document(
        client=client,
        session_factory=session_factory,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    node_id = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()["tree"]["children"][0]["id"]
    question_id = UUID(
        client.post(
            f"/api/v1/knowledge-nodes/{node_id}/questions",
            json={"intent": "explain"},
        ).json()["question_id"]
    )

    from app.retrieval.retriever import Retriever
    from app.services.question_service import QuestionService

    with session_factory() as session:
        QuestionService(session, retriever=Retriever(session, embedding_provider, vector_store)).answer(question_id)
        session.commit()

    body = client.get(f"/api/v1/questions/{question_id}").json()

    assert {"intent", "prompt_version", "model", "confidence", "latency_ms", "answer_mode"} <= set(body)
    assert body["prompt_version"] == "node-assistant-v1"
    assert body["latency_ms"] >= 0
    assert body["status"] in {"answered", "insufficient_evidence"}
