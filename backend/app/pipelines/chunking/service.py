from uuid import UUID, uuid5

from app.core.config import settings
from app.pipelines.chunking.contracts import ContentChunkDraft
from app.pipelines.chunking.splitter import split_text
from app.schemas.documents import DocumentSection, ProcessedDocument

CHUNK_NAMESPACE = UUID("6f5a1f5f-1f0f-4d0a-9c1f-5b1d4f7c9a10")


class ChunkingService:
    """Converts parsed sections into stable, retrievable content blocks."""

    def __init__(self, max_characters: int, overlap_characters: int) -> None:
        self._max_characters = max_characters
        self._overlap_characters = overlap_characters

    def chunk_document(self, document: ProcessedDocument, document_id: UUID) -> list[ContentChunkDraft]:
        chunks: list[ContentChunkDraft] = []
        chunk_index = 0
        for section_index, section in enumerate(document.sections):
            if not section.text.strip():
                continue
            for span in split_text(section.text, self._max_characters, self._overlap_characters):
                chunks.append(
                    ContentChunkDraft(
                        id=self._build_chunk_id(document_id, chunk_index),
                        document_id=document_id,
                        section_index=section_index,
                        chunk_index=chunk_index,
                        section_title=section.title,
                        text=span.text,
                        char_start=span.start,
                        char_end=span.end,
                        page_number=_primary_page_number(section),
                        paragraph_index=_primary_paragraph_index(section),
                    )
                )
                chunk_index += 1
        return chunks

    @staticmethod
    def _build_chunk_id(document_id: UUID, chunk_index: int) -> UUID:
        return uuid5(CHUNK_NAMESPACE, f"{document_id}:{chunk_index}")


def _primary_page_number(section: DocumentSection) -> int | None:
    for location in section.source_locations:
        if location.page_number is not None:
            return location.page_number
    return None


def _primary_paragraph_index(section: DocumentSection) -> int | None:
    for location in section.source_locations:
        if location.paragraph_index is not None:
            return location.paragraph_index
    return None


def create_default_chunking_service() -> ChunkingService:
    return ChunkingService(
        max_characters=settings.chunk_max_characters,
        overlap_characters=settings.chunk_overlap_characters,
    )
