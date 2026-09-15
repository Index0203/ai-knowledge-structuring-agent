from pathlib import Path

from app.pipelines.document_processing.contracts import DocumentParser
from app.pipelines.document_processing.errors import UnsupportedDocumentTypeError


class DocumentParserRegistry:
    """Resolves parsers by extension so new formats do not alter the service layer."""

    def __init__(self) -> None:
        self._parsers_by_extension: dict[str, DocumentParser] = {}

    def register(self, parser: DocumentParser) -> None:
        for extension in parser.supported_extensions:
            normalized_extension = extension.lower()
            if normalized_extension in self._parsers_by_extension:
                raise ValueError(f"A parser is already registered for {normalized_extension}.")
            self._parsers_by_extension[normalized_extension] = parser

    def resolve(self, file_path: Path) -> DocumentParser:
        extension = file_path.suffix.lower()
        parser = self._parsers_by_extension.get(extension)
        if parser is None:
            raise UnsupportedDocumentTypeError(f"No document parser is registered for '{extension or 'unknown'}'.")
        return parser
