import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import fitz

from app.pipelines.document_processing.contracts import DocumentProcessingRequest
from app.pipelines.document_processing.errors import DocumentProcessingError, NoExtractableTextError
from app.pipelines.document_processing.headings import (
    TextLine,
    dedupe_key,
    detect_heading_level,
    detect_level,
    estimate_body_size,
    extract_lines,
    is_noise_line,
    is_table_of_contents,
    looks_like_unlabelled_chapter_opener,
    split_noise_label,
    split_inline_items,
    split_numbered_item,
    reattach_trailing_markers,
    next_chapter_prefix,
    repair_label,
    label_title,
    LABEL_SEQUENCE,
    normalize_heading_text,
    split_label_heading,
    strip_opener_noise,
    LABEL_HEADING_LEVEL,
)
from app.pipelines.document_processing.ocr import OcrEngine
from app.schemas.documents import DocumentMetadata, DocumentSection, ProcessedDocument, SourceLocation

logger = logging.getLogger(__name__)

STRUCTURE_SOURCE_OUTLINE = "pdf_outline"
STRUCTURE_SOURCE_HEADINGS = "detected_headings"
STRUCTURE_SOURCE_PAGES = "pages"

MIN_DETECTED_HEADINGS = 2
MIN_PREAMBLE_CHARACTERS = 40
# Body text that a document mis-styles as a heading is usually a full sentence;
# real section titles are short.
MIN_UNNUMBERED_CONTENT_CHARACTERS = 24
PREAMBLE_TITLE = "前言"


@dataclass(frozen=True)
class PageContent:
    page_number: int
    text: str
    lines: list[TextLine]
    from_ocr: bool


class PdfDocumentParser:
    """PDF parser that keeps the document outline so the map can mirror it."""

    name = "pymupdf"
    supported_extensions = frozenset({".pdf"})

    def __init__(
        self,
        ocr_engine: OcrEngine | None = None,
        *,
        ocr_min_text_characters: int = 12,
        ocr_dpi: int = 200,
        ocr_max_pages: int = 50,
    ) -> None:
        self._ocr_engine = ocr_engine
        self._ocr_min_text_characters = ocr_min_text_characters
        self._ocr_dpi = ocr_dpi
        self._ocr_max_pages = ocr_max_pages

    def parse(self, request: DocumentProcessingRequest) -> ProcessedDocument:
        try:
            with fitz.open(request.file_path) as pdf_document:
                title = self._get_title(pdf_document.metadata, Path(request.original_filename).stem)
                pages = self._extract_pages(pdf_document)
                sections, structure_source = self._build_sections(pdf_document, pages)
                if not sections:
                    raise self._build_empty_document_error(pdf_document)
                return ProcessedDocument(
                    title=title,
                    sections=sections,
                    metadata=DocumentMetadata(
                        source_document_id=request.document_id,
                        original_filename=request.original_filename,
                        media_type=request.media_type,
                        parser_name=self.name,
                        structure_source=structure_source,
                        page_count=pdf_document.page_count,
                        ocr_page_count=sum(1 for page in pages if page.from_ocr),
                        extracted_at=datetime.now(UTC),
                    ),
                )
        except (fitz.FileDataError, OSError, RuntimeError) as error:
            raise DocumentProcessingError("The PDF could not be processed.") from error

    # ------------------------------------------------------------------ pages

    def _extract_pages(self, pdf_document: fitz.Document) -> list[PageContent]:
        pages: list[PageContent] = []
        ocr_page_count = 0
        for page_index, page in enumerate(pdf_document):
            text = page.get_text("text").strip()
            lines = (
                _split_lines(
                    [line for line in extract_lines(page) if not is_noise_line(line.text)]
                )
                if text
                else []
            )
            from_ocr = False
            if len(text) < self._ocr_min_text_characters and ocr_page_count < self._ocr_max_pages:
                ocr_text = self._run_ocr(page)
                if ocr_text:
                    text = ocr_text
                    lines = _split_lines(
                        [
                            TextLine(text=line)
                            for line in ocr_text.splitlines()
                            if line.strip() and not is_noise_line(line)
                        ]
                    )
                    from_ocr = True
                    ocr_page_count += 1
            if text:
                pages.append(PageContent(page_number=page_index + 1, text=text, lines=lines, from_ocr=from_ocr))
        return pages

    def _run_ocr(self, page: fitz.Page) -> str:
        if self._ocr_engine is None:
            return ""
        try:
            return self._ocr_engine.extract_page_text(page, self._ocr_dpi)
        except Exception as error:  # noqa: BLE001 - a failed page must not fail the document
            logger.warning("OCR failed for one page and was skipped: %s", error)
            return ""

    # --------------------------------------------------------------- sections

    def _build_sections(
        self, pdf_document: fitz.Document, pages: list[PageContent]
    ) -> tuple[list[DocumentSection], str]:
        outline_sections = self._sections_from_outline(pdf_document, pages)
        if outline_sections:
            return outline_sections, STRUCTURE_SOURCE_OUTLINE

        heading_sections = self._sections_from_headings(pages)
        if heading_sections:
            return heading_sections, STRUCTURE_SOURCE_HEADINGS

        return self._sections_from_pages(pages), STRUCTURE_SOURCE_PAGES

    @staticmethod
    def _sections_from_outline(pdf_document: fitz.Document, pages: list[PageContent]) -> list[DocumentSection]:
        """Use the embedded PDF bookmark tree when the document has one."""
        try:
            outline = pdf_document.get_toc(simple=True)
        except Exception:  # noqa: BLE001 - broken outlines are not fatal
            return []
        entries = [(level, title.strip(), page) for level, title, page in outline if title and title.strip()]
        if len(entries) < MIN_DETECTED_HEADINGS:
            return []

        text_by_page = {page.page_number: page.text for page in pages}
        last_page = max(text_by_page, default=1)
        sections: list[DocumentSection] = []
        for index, (level, title, start_page) in enumerate(entries):
            end_page = entries[index + 1][2] if index + 1 < len(entries) else last_page
            body = "\n".join(
                text_by_page[page_number]
                for page_number in range(start_page, max(end_page, start_page) + 1)
                if page_number in text_by_page
            ).strip()
            sections.append(
                DocumentSection(
                    title=normalize_heading_text(title),
                    level=max(1, min(int(level), 6)),
                    text=body,
                    source_locations=[SourceLocation(page_number=max(start_page, 1))],
                )
            )
        kept = [section for section in sections if section.text]
        return _drop_mis_styled_content(kept, keep_text=False)

    def _sections_from_headings(self, pages: list[PageContent]) -> list[DocumentSection]:
        """Split the text at lines that look like headings."""
        content_pages = [page for page in pages if not is_table_of_contents(page.lines)]
        all_lines = [line for page in content_pages for line in page.lines]
        body_size = estimate_body_size(all_lines)
        chapter_openers = self._chapter_openers(content_pages)

        sections: list[DocumentSection] = []
        heading_count = 0
        current_title: str | None = None
        current_level = 1
        current_page = pages[0].page_number if pages else 1
        current_text: list[str] = []
        last_chapter_title: str | None = None
        label_block_active = False
        seen_labels: set[str] = set()

        def flush() -> None:
            if current_title is None:
                return
            sections.append(
                DocumentSection(
                    title=normalize_heading_text(current_title),
                    level=current_level,
                    text="\n".join(line for line in current_text if line.strip()).strip(),
                    source_locations=[SourceLocation(page_number=current_page)],
                )
            )

        for page in content_pages:
            for line in page.lines:
                text = line.text.strip()
                if not text:
                    continue
                if text == chapter_openers.get(page.page_number):
                    flush()
                    heading_count += 1
                    seen_labels = set()
                    label_block_active = False
                    prefix = next_chapter_prefix(last_chapter_title)
                    opener_title = strip_opener_noise(text)
                    current_title = f"{prefix} {opener_title}".strip() if prefix else opener_title
                    current_level = 1
                    current_page = page.page_number
                    current_text = []
                    last_chapter_title = current_title
                    continue
                label_heading = split_label_heading(text)
                if label_heading is not None:
                    label, inline_body = label_heading
                    flush()
                    heading_count += 1
                    if label in LABEL_SEQUENCE:
                        seen_labels.add(label)
                    current_title = label_title(label, inline_body)
                    current_level = LABEL_HEADING_LEVEL
                    current_page = page.page_number
                    current_text = [inline_body] if inline_body else []
                    label_block_active = True
                    continue
                noise_label = split_noise_label(text)
                if noise_label is not None:
                    _, inline_body = noise_label
                    repaired = repair_label(seen_labels, inline_body)
                    if repaired is not None:
                        flush()
                        heading_count += 1
                        seen_labels.add(repaired)
                        current_title = repaired
                        current_level = LABEL_HEADING_LEVEL
                        current_page = page.page_number
                        current_text = [inline_body.strip()] if inline_body.strip() else []
                        label_block_active = True
                        continue
                level = detect_level(line, None if page.from_ocr else body_size)
                if level is not None:
                    if level == LABEL_HEADING_LEVEL + 1 and not label_block_active:
                        # A numbered list outside a labelled block is body text, not a node.
                        if current_title is None:
                            current_title = PREAMBLE_TITLE
                            current_level = 1
                            current_page = page.page_number
                        current_text.append(text)
                        continue
                    flush()
                    heading_count += 1
                    if level <= 2:
                        seen_labels = set()
                    if level != LABEL_HEADING_LEVEL + 1:
                        label_block_active = False
                        current_title = text
                        current_text = []
                    else:
                        # A numbered point keeps its marker as title and its wording as body.
                        item_title, item_body = split_numbered_item(text)
                        current_title = item_title
                        current_text = [item_body] if item_body else []
                    current_level = level
                    current_page = page.page_number
                    if level == 1:
                        last_chapter_title = normalize_heading_text(text)
                    continue
                if current_title is None:
                    current_title = PREAMBLE_TITLE
                    current_level = 1
                    current_page = page.page_number
                current_text.append(text)
        flush()

        if heading_count < MIN_DETECTED_HEADINGS:
            return []
        kept_sections = _deduplicate_sections(
            [section for section in sections if _keep_section(section)]
        )
        folded = _drop_mis_styled_content(kept_sections, keep_text=True)
        return _align_preamble_level(folded)

    @staticmethod
    def _chapter_openers(pages: list[PageContent]) -> dict[int, str]:
        """Chapter openers whose 「第X章」 marker the scan lost keep their own node."""
        openers: dict[int, str] = {}
        for page in pages:
            opener = looks_like_unlabelled_chapter_opener([line.text for line in page.lines])
            if opener:
                openers[page.page_number] = opener
        return openers

    @staticmethod
    def _sections_from_pages(pages: list[PageContent]) -> list[DocumentSection]:
        return [
            DocumentSection(
                title=f"Page {page.page_number}",
                level=1,
                text=page.text,
                source_locations=[SourceLocation(page_number=page.page_number)],
            )
            for page in pages
            if page.text.strip()
        ]

    # ------------------------------------------------------------------ misc

    @staticmethod
    def _get_title(metadata: dict[str, str | None], fallback_title: str) -> str:
        return (metadata.get("title") or fallback_title).strip() or fallback_title

    @staticmethod
    def _build_empty_document_error(pdf_document: fitz.Document) -> DocumentProcessingError:
        """Explain why a PDF produced no text so the client can guide the user."""
        page_count = pdf_document.page_count
        if page_count == 0:
            return DocumentProcessingError("The PDF contains no pages.")
        image_page_count = sum(1 for page in pdf_document if page.get_images(full=True))
        if image_page_count:
            return NoExtractableTextError(
                f"The PDF has no extractable text layer: {image_page_count} of {page_count} pages are images. "
                "Scanned documents require OCR.",
                page_count=page_count,
                image_page_count=image_page_count,
            )
        return NoExtractableTextError(
            f"The PDF has no extractable text layer across {page_count} pages.",
            page_count=page_count,
        )


def _keep_section(section: DocumentSection) -> bool:
    """Heading nodes stay in the outline even when they have no body text yet."""
    if section.title == PREAMBLE_TITLE:
        return len(section.text.strip()) >= MIN_PREAMBLE_CHARACTERS
    return True


def _align_preamble_level(sections: list[DocumentSection]) -> list[DocumentSection]:
    """Front matter sits beside the chapters, not above them.

    A document that opens with an abstract before its numbered sections would
    otherwise nest every chapter underneath the preamble node, which is what the
    knowledge map mirrors. The DOCX parser aligns its front matter the same way.
    """
    if len(sections) < 2 or sections[0].title != PREAMBLE_TITLE:
        return sections
    first_heading_level = sections[1].level
    if first_heading_level > sections[0].level:
        sections[0] = sections[0].model_copy(update={"level": first_heading_level})
    return sections


def _drop_mis_styled_content(
    sections: list[DocumentSection], *, keep_text: bool
) -> list[DocumentSection]:
    """Fold content that a document mis-styles as a heading into the item above it.

    Word builds bookmarks from heading *styles*, so a body paragraph that
    inherits one shows up in the outline at the same level as the numbered item
    above it (for example `1.优化包装策略` followed by three plain sentences).
    The map mirrors the document's structure, so those paragraphs stay part of
    the numbered item instead of becoming nodes of their own. Short, unnumbered
    entries are real headings such as `参考文献`, so they are kept.

    `keep_text` carries the dropped wording over to the numbered item, which the
    bookmark path does not need: its sections already span every page between
    their own start page and the next surviving entry.
    """
    folded: list[DocumentSection] = []
    anchor_index: int | None = None
    for section in sections:
        if anchor_index is not None and folded[anchor_index].level != section.level:
            anchor_index = None
        if section.level >= 2 and detect_heading_level(section.title) is not None:
            folded.append(section)
            anchor_index = len(folded) - 1
            continue
        is_body_text = (
            anchor_index is not None
            and detect_heading_level(section.title) is None
            and len(section.title) >= MIN_UNNUMBERED_CONTENT_CHARACTERS
        )
        if not is_body_text:
            folded.append(section)
            continue
        if keep_text:
            anchor = folded[anchor_index]
            merged_text = "\n".join(
                part for part in (anchor.text, section.text) if part.strip()
            )
            folded[anchor_index] = anchor.model_copy(update={"text": merged_text})
    return folded


def _split_lines(lines: list[TextLine]) -> list[TextLine]:
    """Repair OCR line breaks, then split inline numbered points into their own lines."""
    repaired = reattach_trailing_markers(lines)
    return [
        TextLine(text=part, size=line.size)
        for line in repaired
        for part in split_inline_items(line.text)
        if part and not is_noise_line(part)
    ]


def _deduplicate_sections(sections: list[DocumentSection]) -> list[DocumentSection]:
    """Collapse repeated chapter headings (running headers), never repeated sub-sections.

    Labels such as 传统发展痛点 legitimately reappear in every section, so only
    first-level headings are deduplicated.
    """
    by_key: dict[str, int] = {}
    deduplicated: list[DocumentSection] = []
    for section in sections:
        if section.level != 1:
            deduplicated.append(section)
            continue
        key = dedupe_key(section.title)
        existing_index = by_key.get(key)
        if existing_index is None:
            by_key[key] = len(deduplicated)
            deduplicated.append(section)
            continue
        if len(section.text) > len(deduplicated[existing_index].text):
            deduplicated[existing_index] = section
    return deduplicated
