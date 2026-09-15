from uuid import UUID

from pydantic import BaseModel, Field


class ContentChunkDraft(BaseModel):
    """One retrievable content block, still tied to its source location."""

    id: UUID
    document_id: UUID
    section_index: int = Field(ge=0)
    chunk_index: int = Field(ge=0)
    section_title: str
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    paragraph_index: int | None = Field(default=None, ge=0)
