from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    status: str
    error_message: str | None
    error_code: str | None
    page_count: int | None
    paragraph_count: int | None
    ocr_page_count: int | None
    chunk_count: int
    embedding_model: str | None
    tree_status: str
    tree_error: str | None
    tree_mode: str | None
    created_at: datetime
    indexed_at: datetime | None
    tree_built_at: datetime | None


class ProcessingAcceptedResponse(BaseModel):
    document_id: UUID
    status: str
