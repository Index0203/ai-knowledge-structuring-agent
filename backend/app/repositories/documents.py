from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: Document) -> Document:
        self._session.add(document)
        self._session.flush()
        return document

    def get(self, document_id: UUID) -> Document | None:
        return self._session.get(Document, document_id)

    def list_recent(self, limit: int = 20) -> list[Document]:
        return (
            self._session.query(Document)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .all()
        )
