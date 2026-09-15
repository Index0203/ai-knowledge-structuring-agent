"""Document Analyst Agent — turns a stored file into sections, statistics and an outline."""

from pathlib import Path
from uuid import UUID

from app.agents.workflow.state import DocumentDigest, WorkflowDependencies
from app.pipelines.document_processing.errors import DocumentProcessingError
from app.pipelines.document_processing.service import (
    DocumentProcessingService,
    create_default_document_processing_service,
)
from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository
from app.schemas.documents import DocumentSection, ProcessedDocument

MAX_OUTLINE_ENTRIES = 25


class DocumentAnalystAgent:
    """Understanding stage: no model required, but it is the source of every later fact."""

    def __init__(self, processing_service: DocumentProcessingService | None = None) -> None:
        self._processing = processing_service or create_default_document_processing_service()

    def analyse(
        self,
        deps: WorkflowDependencies,
        document_id: UUID,
    ) -> tuple[DocumentDigest, ProcessedDocument, list[DocumentSection]]:
        document = DocumentRepository(deps.session).get(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} does not exist.")

        file_path = Path(deps.upload_dir) / document.storage_key
        try:
            processed = self._processing.process(
                file_path=file_path,
                original_filename=document.original_filename,
                media_type=document.media_type,
                document_id=document.id,
            )
        except DocumentProcessingError as error:
            raise ValueError(str(error)) from error

        sections = [section for section in processed.sections if section.text.strip()]
        warnings: list[str] = []
        if not sections:
            warnings.append("解析后没有任何可用文本")
        if processed.metadata.structure_source == "pages":
            warnings.append("未能识别章节结构，已退回按页分节")
        if processed.metadata.ocr_page_count:
            warnings.append(f"{processed.metadata.ocr_page_count} 页通过 OCR 识别，可能含识别噪声")

        digest = DocumentDigest(
            document_id=document.id,
            title=processed.title,
            structure_source=processed.metadata.structure_source,
            parser_name=processed.metadata.parser_name,
            page_count=processed.metadata.page_count,
            paragraph_count=processed.metadata.paragraph_count,
            ocr_page_count=processed.metadata.ocr_page_count,
            section_count=len(sections),
            chunk_count=ChunkRepository(deps.session).count_by_document(document.id),
            outline=[
                f"{'  ' * max(section.level - 1, 0)}- {section.title}" for section in sections[:MAX_OUTLINE_ENTRIES]
            ],
            warnings=warnings,
        )
        return digest, processed, sections
