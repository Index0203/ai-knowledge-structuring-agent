from uuid import UUID

from app.pipelines.chunking.service import ChunkingService
from app.schemas.documents import DocumentMetadata, DocumentSection, ProcessedDocument, SourceLocation

DOCUMENT_ID = UUID("11111111-1111-1111-1111-111111111111")


def make_document(text: str, page_number: int = 1) -> ProcessedDocument:
    return ProcessedDocument(
        title="Evidence Report",
        sections=[
            DocumentSection(
                title="Findings",
                level=1,
                text=text,
                source_locations=[SourceLocation(page_number=page_number)],
            )
        ],
        metadata=DocumentMetadata(
            original_filename="report.pdf",
            media_type="application/pdf",
            parser_name="pymupdf",
        ),
    )


def test_short_section_becomes_one_chunk_that_keeps_its_source_location() -> None:
    chunks = ChunkingService(max_characters=200, overlap_characters=50).chunk_document(
        make_document("First paragraph.\n\nSecond paragraph."), DOCUMENT_ID
    )

    assert len(chunks) == 1
    assert chunks[0].text == "First paragraph.\n\nSecond paragraph."
    assert chunks[0].section_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len("First paragraph.\n\nSecond paragraph.")


def test_long_section_is_split_into_overlapping_windows() -> None:
    paragraph = " ".join(f"Sentence {index} about evidence." for index in range(20))
    chunks = ChunkingService(max_characters=120, overlap_characters=30).chunk_document(
        make_document(paragraph), DOCUMENT_ID
    )

    assert len(chunks) > 1
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(len(chunk.text) <= 120 for chunk in chunks)


def test_chunk_ids_are_deterministic_for_the_same_document() -> None:
    service = ChunkingService(max_characters=100, overlap_characters=20)
    document = make_document("Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph.")

    first = service.chunk_document(document, DOCUMENT_ID)
    second = service.chunk_document(document, DOCUMENT_ID)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
