from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository
from app.schemas.pipeline import DocumentStatusResponse, ProcessingAcceptedResponse


class DocumentNotFoundError(Exception):
    """Raised when a document id has no persisted document."""


def get_document_status(session: Session, document_id: UUID) -> DocumentStatusResponse:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} does not exist.")
    chunks = ChunkRepository(session)
    return DocumentStatusResponse(
        document_id=document.id,
        original_filename=document.original_filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        status=document.status,
        error_message=document.error_message,
        error_code=document.error_code,
        page_count=document.page_count,
        paragraph_count=document.paragraph_count,
        ocr_page_count=document.ocr_page_count,
        chunk_count=chunks.count_by_document(document.id),
        embedding_model=chunks.embedding_model_for_document(document.id),
        tree_status=document.tree_status,
        tree_error=document.tree_error,
        tree_mode=document.tree_mode,
        created_at=document.created_at,
        indexed_at=document.indexed_at,
        tree_built_at=document.tree_built_at,
    )


def request_indexing(session: Session, document_id: UUID, dispatcher) -> ProcessingAcceptedResponse:
    document = _require_document(session, document_id)
    document.status = "indexing"
    document.error_message = None
    document.error_code = None
    session.commit()
    try:
        dispatcher(document.id)
    except Exception as error:  # noqa: BLE001 - keep the document state truthful
        document.status = "failed"
        document.error_message = str(error)
        session.commit()
        raise
    return ProcessingAcceptedResponse(document_id=document.id, status=document.status)


def request_tree_build(session: Session, document_id: UUID, dispatcher) -> ProcessingAcceptedResponse:
    document = _require_document(session, document_id)
    document.tree_status = "building"
    document.tree_error = None
    session.commit()
    try:
        dispatcher(document.id)
    except Exception as error:  # noqa: BLE001 - keep the document state truthful
        document.tree_status = "failed"
        document.tree_error = str(error)
        session.commit()
        raise
    return ProcessingAcceptedResponse(document_id=document.id, status=document.tree_status)


def _require_document(session: Session, document_id: UUID):
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document {document_id} does not exist.")
    return document
