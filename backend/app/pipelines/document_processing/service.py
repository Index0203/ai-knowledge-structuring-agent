from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.pipelines.document_processing.contracts import DocumentProcessingRequest
from app.pipelines.document_processing.ocr import create_ocr_engine
from app.pipelines.document_processing.parsers import DocxDocumentParser, PdfDocumentParser
from app.pipelines.document_processing.registry import DocumentParserRegistry
from app.schemas.documents import ProcessedDocument


class DocumentProcessingService:
    """Application service intended to be invoked by asynchronous document workers."""

    def __init__(self, parser_registry: DocumentParserRegistry) -> None:
        self._parser_registry = parser_registry

    def process(
        self,
        file_path: Path,
        original_filename: str,
        media_type: str,
        document_id: UUID | None = None,
    ) -> ProcessedDocument:
        request = DocumentProcessingRequest(
            file_path=file_path,
            original_filename=original_filename,
            media_type=media_type,
            document_id=document_id,
        )
        return self._parser_registry.resolve(file_path).parse(request)


def create_default_document_processing_service() -> DocumentProcessingService:
    registry = DocumentParserRegistry()
    registry.register(
        PdfDocumentParser(
            create_ocr_engine(),
            ocr_min_text_characters=settings.ocr_min_text_characters,
            ocr_dpi=settings.ocr_dpi,
            ocr_max_pages=settings.ocr_max_pages,
        )
    )
    registry.register(DocxDocumentParser())
    return DocumentProcessingService(registry)
