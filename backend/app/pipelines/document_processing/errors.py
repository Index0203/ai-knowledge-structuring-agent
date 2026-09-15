class DocumentProcessingError(Exception):
    """Raised when a document cannot be converted into the common contract."""

    error_code = "processing_failed"


class UnsupportedDocumentTypeError(DocumentProcessingError):
    """Raised when no registered parser supports the document extension."""

    error_code = "unsupported_format"


class NoExtractableTextError(DocumentProcessingError):
    """Raised when a document has no machine-readable text layer."""

    error_code = "no_text_layer"

    def __init__(
        self,
        message: str,
        *,
        page_count: int | None = None,
        image_page_count: int | None = None,
    ) -> None:
        super().__init__(message)
        self.page_count = page_count
        self.image_page_count = image_page_count
