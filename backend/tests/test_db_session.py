"""Session boundary: commits on success, rolls back on failure."""

from uuid import uuid4

import pytest

from app import db
from app.db.session import session_scope
from app.models.document import Document


def make_document() -> Document:
    return Document(
        id=uuid4(),
        original_filename="report.pdf",
        media_type="application/pdf",
        storage_key="report.pdf",
        size_bytes=1,
    )


def test_session_scope_commits(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(db.session, "SessionLocal", session_factory)
    document = make_document()

    with session_scope() as session:
        session.add(document)

    with session_factory() as session:
        assert session.get(Document, document.id) is not None


def test_session_scope_rolls_back_and_reraises(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(db.session, "SessionLocal", session_factory)
    document = make_document()

    with pytest.raises(RuntimeError, match="boom"):
        with session_scope() as session:
            session.add(document)
            session.flush()
            raise RuntimeError("boom")

    with session_factory() as session:
        assert session.get(Document, document.id) is None
