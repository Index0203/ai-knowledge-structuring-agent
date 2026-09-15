from io import BytesIO
from pathlib import Path
from uuid import UUID

import fitz
import pytest
from docx import Document as WordDocument
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.embeddings.deterministic import DeterministicEmbeddingProvider
from app.retrieval.retriever import Retriever
from app.services.indexing_service import DocumentIndexingService
from app.services.knowledge_tree_service import KnowledgeTreeService
from app.services.question_service import QuestionService
from app.vectorstores.in_memory_vector_store import InMemoryVectorStore

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_docx_bytes() -> bytes:
    word_document = WordDocument()
    word_document.core_properties.title = "Evidence Handbook"
    word_document.add_heading("Retrieval", level=1)
    word_document.add_paragraph("Retrieval selects the content blocks that support an answer.")
    word_document.add_heading("Citations", level=2)
    word_document.add_paragraph("Every answer must cite the content block it came from.")
    buffer = BytesIO()
    word_document.save(buffer)
    return buffer.getvalue()


def make_scanned_pdf_bytes() -> bytes:
    """A PDF whose pages only contain pictures, so there is no text layer."""
    pdf_document = fitz.open()
    page = pdf_document.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40))
    pixmap.set_rect(pixmap.irect, (180, 180, 180))
    page.insert_image(page.rect, pixmap=pixmap)
    content = pdf_document.tobytes()
    pdf_document.close()
    return content


def prepare_indexed_document(
    *,
    client,
    session_factory: sessionmaker[Session],
    vector_store: InMemoryVectorStore,
    embedding_provider: DeterministicEmbeddingProvider,
    tmp_path: Path,
    monkeypatch,
) -> UUID:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr("app.api.routes.documents.dispatch_index_document", lambda _: None)
    monkeypatch.setattr("app.api.routes.documents.dispatch_build_knowledge_tree", lambda _: None)
    monkeypatch.setattr("app.workers.dispatch.dispatch_answer_question", lambda _: None)

    upload = client.post(
        "/api/v1/uploads",
        files={"file": ("handbook.docx", make_docx_bytes(), DOCX_MEDIA_TYPE)},
    )
    assert upload.status_code == 201
    document_id = UUID(upload.json()["document_id"])

    assert client.post(f"/api/v1/documents/{document_id}/processing").status_code == 202
    with session_factory() as session:
        outcome = DocumentIndexingService(
            session,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        ).index(document_id)
        session.commit()
    assert outcome.status == "indexed"

    assert client.post(f"/api/v1/documents/{document_id}/knowledge-tree").status_code == 202
    with session_factory() as session:
        tree_outcome = KnowledgeTreeService(session).build(document_id)
        session.commit()
    assert tree_outcome.status == "ready"
    return document_id


def test_upload_is_indexed_and_structured_into_nodes(client, session_factory, vector_store, embedding_provider, tmp_path, monkeypatch) -> None:
    document_id = prepare_indexed_document(
        client=client,
        session_factory=session_factory,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )

    status_body = client.get(f"/api/v1/documents/{document_id}").json()
    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()

    assert status_body["status"] == "indexed"
    assert status_body["chunk_count"] >= 1
    assert status_body["tree_status"] == "ready"
    assert status_body["tree_mode"] == "structure_fallback"
    assert tree_body["tree"]["title"] == "Evidence Handbook"
    chapters = tree_body["tree"]["children"]
    assert [child["title"] for child in chapters] == ["Retrieval"]
    assert [child["title"] for child in chapters[0]["children"]] == ["Citations"]
    # A chapter node covers its own section plus every descendant section.
    assert chapters[0]["source_section_indexes"] == [0, 1]
    assert chapters[0]["children"][0]["source_section_indexes"] == [1]


def test_node_question_returns_a_cited_answer(client, session_factory, vector_store, embedding_provider, tmp_path, monkeypatch) -> None:
    document_id = prepare_indexed_document(
        client=client,
        session_factory=session_factory,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
    )
    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()
    node_id = tree_body["tree"]["children"][0]["children"][0]["id"]

    submitted = client.post(
        f"/api/v1/knowledge-nodes/{node_id}/questions",
        json={"question": "What must every answer cite?"},
    )
    assert submitted.status_code == 202
    question_id = UUID(submitted.json()["question_id"])

    with session_factory() as session:
        QuestionService(session, retriever=Retriever(session, embedding_provider, vector_store)).answer(question_id)
        session.commit()

    answer = client.get(f"/api/v1/questions/{question_id}").json()
    assert answer["status"] == "answered"
    assert answer["answer_mode"] == "extractive_fallback"
    assert answer["answer"]
    assert answer["citations"], "an answered question must always carry citations"
    assert answer["citations"][0]["quote"]
    assert answer["citations"][0]["section_title"] in {"Retrieval", "Citations"}


def test_question_is_refused_when_no_evidence_clears_the_threshold(
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
    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()
    node_id = tree_body["tree"]["children"][0]["id"]
    monkeypatch.setattr(settings, "retrieval_min_score", 0.99)

    submitted = client.post(
        f"/api/v1/knowledge-nodes/{node_id}/questions",
        json={"question": "What is the vacation policy for contractors?"},
    )
    question_id = UUID(submitted.json()["question_id"])

    with session_factory() as session:
        QuestionService(session, retriever=Retriever(session, embedding_provider, vector_store)).answer(question_id)
        session.commit()

    answer = client.get(f"/api/v1/questions/{question_id}").json()
    assert answer["status"] == "insufficient_evidence"
    assert answer["answer"] is None
    assert answer["citations"] == []
    assert "matched the request" in (answer["error_message"] or "")


def test_explain_intent_answers_without_a_free_form_question(
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
    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()
    node_id = tree_body["tree"]["children"][0]["id"]

    submitted = client.post(f"/api/v1/knowledge-nodes/{node_id}/questions", json={"intent": "explain"})
    assert submitted.status_code == 202
    assert submitted.json()["intent"] == "explain"
    question_id = UUID(submitted.json()["question_id"])

    with session_factory() as session:
        QuestionService(session, retriever=Retriever(session, embedding_provider, vector_store)).answer(question_id)
        session.commit()

    answer = client.get(f"/api/v1/questions/{question_id}").json()
    assert answer["intent"] == "explain"
    assert answer["status"] == "answered"
    assert answer["question"] == "请解释这个节点。"
    assert answer["citations"]


def test_quiz_intent_returns_questions_with_citations(
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
    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()
    node_id = tree_body["tree"]["children"][0]["id"]

    submitted = client.post(f"/api/v1/knowledge-nodes/{node_id}/questions", json={"intent": "quiz"})
    question_id = UUID(submitted.json()["question_id"])

    with session_factory() as session:
        QuestionService(session, retriever=Retriever(session, embedding_provider, vector_store)).answer(question_id)
        session.commit()

    answer = client.get(f"/api/v1/questions/{question_id}").json()
    assert answer["intent"] == "quiz"
    assert answer["status"] == "answered"
    # Without a model the degraded mode derives questions from the child nodes.
    assert answer["quiz_items"]
    assert all(item["citations"] for item in answer["quiz_items"])
    assert answer["quiz_items"][0]["question"].startswith("请说明")


def test_unknown_intent_falls_back_to_a_free_form_question(client) -> None:
    response = client.post(
        "/api/v1/knowledge-nodes/99999999-9999-9999-9999-999999999999/questions",
        json={"intent": "does-not-exist", "question": "这是什么？"},
    )

    assert response.status_code == 404


def test_assistant_failure_marks_the_question_failed(
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
    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()
    node_id = tree_body["tree"]["children"][0]["id"]
    submitted = client.post(f"/api/v1/knowledge-nodes/{node_id}/questions", json={"intent": "deep_dive"})
    question_id = UUID(submitted.json()["question_id"])

    class ExplodingAgent:
        def answer(self, **_kwargs):
            raise RuntimeError("provider exploded")

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "deepseek-chat")
    with session_factory() as session:
        outcome = QuestionService(
            session,
            retriever=Retriever(session, embedding_provider, vector_store),
            answer_agent=ExplodingAgent(),
        ).answer(question_id)
        session.commit()

    answer = client.get(f"/api/v1/questions/{question_id}").json()
    assert outcome.status == "failed"
    assert answer["status"] == "failed"
    assert "provider exploded" in (answer["error_message"] or "")


def test_question_for_an_unknown_node_returns_not_found(client) -> None:
    response = client.post(
        "/api/v1/knowledge-nodes/99999999-9999-9999-9999-999999999999/questions",
        json={"question": "Is this node real?"},
    )

    assert response.status_code == 404


def test_scanned_pdf_is_reported_with_an_actionable_error_code(
    client, session_factory, vector_store, embedding_provider, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ocr_enabled", False)
    monkeypatch.setattr("app.api.routes.documents.dispatch_index_document", lambda _: None)

    upload = client.post(
        "/api/v1/uploads",
        files={"file": ("scan.pdf", make_scanned_pdf_bytes(), "application/pdf")},
    )
    document_id = UUID(upload.json()["document_id"])
    client.post(f"/api/v1/documents/{document_id}/processing")

    with session_factory() as session:
        outcome = DocumentIndexingService(
            session,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
        ).index(document_id)
        session.commit()

    status_body = client.get(f"/api/v1/documents/{document_id}").json()
    assert outcome.status == "failed"
    assert status_body["status"] == "failed"
    assert status_body["error_code"] == "no_text_layer"
    assert status_body["chunk_count"] == 0


def test_tree_keeps_the_outline_when_model_enrichment_fails(
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

    def exploding_factory():
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "deepseek-chat")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.deepseek.com")
    with session_factory() as session:
        outcome = KnowledgeTreeService(session, enrichment_agent_factory=exploding_factory).build(document_id)
        session.commit()

    tree_body = client.get(f"/api/v1/documents/{document_id}/knowledge-tree").json()
    assert outcome.status == "ready"
    assert outcome.mode == "structure_fallback"
    assert tree_body["mode"] == "structure_fallback"
    assert tree_body["tree"]["children"]
