from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.embeddings.contracts import EmbeddingProvider
from app.embeddings.factory import create_embedding_provider
from app.models.document import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_INDEXED,
    DOCUMENT_STATUS_INDEXING,
    utc_now,
)
from app.pipelines.chunking.service import ChunkingService, create_default_chunking_service
from app.pipelines.document_processing.errors import DocumentProcessingError
from app.pipelines.document_processing.service import (
    DocumentProcessingService,
    create_default_document_processing_service,
)
from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository
from app.vectorstores.contracts import VectorRecord, VectorStore
from app.vectorstores.factory import create_vector_store


@dataclass(frozen=True)
class IndexingOutcome:
    document_id: UUID
    status: str
    chunk_count: int
    embedding_model: str
    error_message: str | None = None


class DocumentIndexingService:
    """Parses one stored document, chunks it, embeds it and refreshes its vector index."""

    def __init__(
        self,
        session: Session,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        chunking_service: ChunkingService | None = None,
        processing_service: DocumentProcessingService | None = None,
    ) -> None:
        self._session = session
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._chunking = chunking_service or create_default_chunking_service()
        self._processing = processing_service or create_default_document_processing_service()

    def index(self, document_id: UUID) -> IndexingOutcome:
        documents = DocumentRepository(self._session)
        document = documents.get(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} does not exist.")

        document.status = DOCUMENT_STATUS_INDEXING
        document.error_message = None
        self._session.flush()

        try:
            processed = self._processing.process(
                file_path=self._resolve_path(document.storage_key),
                original_filename=document.original_filename,
                media_type=document.media_type,
                document_id=document.id,
            )
            chunk_count = self.index_processed_document(document.id, processed)

            document.status = DOCUMENT_STATUS_INDEXED
            document.indexed_at = utc_now()
            document.error_code = None
            document.page_count = processed.metadata.page_count
            document.paragraph_count = processed.metadata.paragraph_count
            document.ocr_page_count = processed.metadata.ocr_page_count
            self._session.flush()
            return IndexingOutcome(
                document_id=document.id,
                status=DOCUMENT_STATUS_INDEXED,
                chunk_count=chunk_count,
                embedding_model=self._embeddings.name,
            )
        except (DocumentProcessingError, OSError, ValueError) as error:
            document.status = DOCUMENT_STATUS_FAILED
            document.error_message = str(error)
            document.error_code = getattr(error, "error_code", "processing_failed")
            self._session.flush()
            return IndexingOutcome(
                document_id=document.id,
                status=DOCUMENT_STATUS_FAILED,
                chunk_count=0,
                embedding_model=self._embeddings.name,
                error_message=str(error),
            )

    def index_processed_document(self, document_id: UUID, processed) -> int:
        """(Re)build chunks and vectors from an already parsed document.

        The knowledge workflow calls this when its sections no longer match the stored
        chunks, so node evidence never points at a stale section index.
        """
        drafts = self._chunking.chunk_document(processed, document_id)
        if not drafts:
            raise DocumentProcessingError("The document contains no extractable text.")
        ChunkRepository(self._session).replace_document_chunks(document_id, drafts, self._embeddings.name)
        self._vector_store.delete_document(document_id)
        self._vector_store.upsert(self._build_vector_records(drafts))
        self._session.flush()
        return len(drafts)

    def _build_vector_records(self, drafts) -> list[VectorRecord]:
        embeddings = self._embeddings.embed_documents([draft.text for draft in drafts])
        records: list[VectorRecord] = []
        for draft, embedding in zip(drafts, embeddings, strict=True):
            metadata: dict[str, str | int | float | bool] = {
                "document_id": str(draft.document_id),
                "section_index": draft.section_index,
                "chunk_index": draft.chunk_index,
            }
            if draft.page_number is not None:
                metadata["page_number"] = draft.page_number
            if draft.paragraph_index is not None:
                metadata["paragraph_index"] = draft.paragraph_index
            records.append(
                VectorRecord(
                    chunk_id=draft.id,
                    document_id=draft.document_id,
                    embedding=embedding,
                    text=draft.text,
                    metadata=metadata,
                )
            )
        return records

    @staticmethod
    def _resolve_path(storage_key: str) -> Path:
        return Path(settings.upload_dir) / storage_key


def create_document_indexing_service(session: Session) -> DocumentIndexingService:
    return DocumentIndexingService(
        session,
        embedding_provider=create_embedding_provider(),
        vector_store=create_vector_store(),
    )
