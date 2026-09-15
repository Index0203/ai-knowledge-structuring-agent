"""OCR fallback for PDF pages that have no text layer."""

import importlib.util
import logging
import re
import shutil

import fitz
from PIL import Image, ImageOps

from app.core.config import settings

logger = logging.getLogger(__name__)

# Structure markers decide which OCR pass to trust: a chapter heading is worth far
# more than a handful of extra characters, because it anchors the knowledge map.
CHAPTER_MARKER = re.compile(r"第\s*[0-9一二三四五六七八九十百千万零〇两=Il|≡]+\s*[章篇部]")
SECTION_MARKER = re.compile(r"^[（(]?[0-9一二三四五六七八九十=Il|≡]{1,3}[)）]?[、.．]\s*\S", re.MULTILINE)
CJK_CHARACTER = re.compile(r"[\u4e00-\u9fff]")


def ocr_text_score(text: str) -> tuple[int, int, int]:
    """Rank an OCR result by how well it preserves document structure."""
    return (
        len(CHAPTER_MARKER.findall(text)),
        len(SECTION_MARKER.findall(text)),
        len(CJK_CHARACTER.findall(text)),
    )


class OcrEngine:
    """Protocol-like base class for page-level OCR engines."""

    name = "ocr"

    def is_available(self) -> bool:
        raise NotImplementedError

    def extract_text(self, image: Image.Image) -> str:
        raise NotImplementedError

    def extract_page_text(self, page: fitz.Page, dpi: int) -> str:
        return self.extract_text(render_page_image(page, dpi))


class TesseractOcrEngine(OcrEngine):
    """Tesseract wrapper. Language data is installed inside the backend image."""

    name = "tesseract"

    def __init__(
        self,
        languages: str,
        psm: int = 3,
        *,
        binarize: bool = False,
        binarize_threshold: int = 165,
        fallback_dpi: int | None = None,
        binary: str = "tesseract",
    ) -> None:
        self._languages = languages
        self._psm = psm
        self._binarize = binarize
        self._binarize_threshold = binarize_threshold
        self._fallback_dpi = fallback_dpi
        self._binary = binary

    def is_available(self) -> bool:
        return importlib.util.find_spec("pytesseract") is not None and shutil.which(self._binary) is not None

    def extract_text(self, image: Image.Image) -> str:
        import pytesseract

        return pytesseract.image_to_string(
            image,
            lang=self._languages,
            config=f"--psm {self._psm}",
        ).strip()

    def extract_page_text(self, page: fitz.Page, dpi: int) -> str:
        primary = self._read_page(page, dpi)
        if self._fallback_dpi is None or self._fallback_dpi == dpi:
            return primary
        alternative = self._read_page(page, self._fallback_dpi)
        if ocr_text_score(alternative) > ocr_text_score(primary):
            logger.debug("Using the %s dpi OCR result for one page.", self._fallback_dpi)
            return alternative
        return primary

    def _read_page(self, page: fitz.Page, dpi: int) -> str:
        image = render_page_image(
            page,
            dpi,
            binarize=self._binarize,
            binarize_threshold=self._binarize_threshold,
        )
        return self.extract_text(image)


def render_page_image(
    page: fitz.Page,
    dpi: int,
    *,
    binarize: bool = False,
    binarize_threshold: int = 165,
) -> Image.Image:
    """Rasterise one PDF page so OCR can read its pixels."""
    zoom = max(dpi, 72) / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    if not binarize:
        return image
    gray = ImageOps.autocontrast(image.convert("L"), cutoff=1)
    return gray.point(lambda value: 255 if value > binarize_threshold else 0)


def create_ocr_engine() -> OcrEngine | None:
    """Return an OCR engine, or None when OCR is disabled or unavailable."""
    if not settings.ocr_enabled:
        return None
    engine = TesseractOcrEngine(
        settings.ocr_languages,
        settings.ocr_psm,
        binarize=settings.ocr_binarize,
        binarize_threshold=settings.ocr_binarize_threshold,
        fallback_dpi=settings.ocr_fallback_dpi,
    )
    if not engine.is_available():
        logger.warning(
            "OCR is enabled but tesseract is not available; scanned pages will be reported as no_text_layer."
        )
        return None
    return engine
