from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SourceLocation(BaseModel):
    """A stable pointer back to a location in the uploaded source document."""

    page_number: int | None = Field(default=None, ge=1)
    paragraph_index: int | None = Field(default=None, ge=0)


class DocumentSection(BaseModel):
    """A normalized structural unit extracted from one document."""

    title: str = Field(min_length=1)
    level: int = Field(ge=1)
    text: str
    source_locations: list[SourceLocation] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    source_document_id: UUID | None = None
    original_filename: str
    media_type: str
    parser_name: str
    structure_source: str | None = Field(default=None)
    page_count: int | None = Field(default=None, ge=0)
    paragraph_count: int | None = Field(default=None, ge=0)
    ocr_page_count: int | None = Field(default=None, ge=0)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProcessedDocument(BaseModel):
    """The common output contract for all document parsers."""

    title: str = Field(min_length=1)
    sections: list[DocumentSection] = Field(default_factory=list)
    metadata: DocumentMetadata
