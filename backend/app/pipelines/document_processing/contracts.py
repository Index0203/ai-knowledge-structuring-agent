from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.schemas.documents import ProcessedDocument


@dataclass(frozen=True)
class DocumentProcessingRequest:
    file_path: Path
    original_filename: str
    media_type: str
    document_id: UUID | None = None


class DocumentParser(Protocol):
    name: str
    supported_extensions: frozenset[str]

    def parse(self, request: DocumentProcessingRequest) -> ProcessedDocument:
        """Convert a supported file into the common ProcessedDocument contract."""
