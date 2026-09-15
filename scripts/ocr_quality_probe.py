"""Compare OCR configurations on specific pages of a document.

Usage (inside the compose network):

    docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" -e PYTHONPATH=/app \
        backend python /scripts/ocr_quality_probe.py <document-id> <first-page> <last-page>
"""

import re
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageOps

import pytesseract

UPLOAD_DIR = Path("data/uploads")
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
HEADING_HINT = re.compile(r"^[（(]?[一二三四五六七八九十=Il|0-9]{1,3}[)）]?[、.．:：]?\s*\S")


def render(page: fitz.Page, dpi: int, preprocess: bool) -> Image.Image:
    zoom = dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    if not preprocess:
        return image
    gray = image.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return gray.point(lambda value: 255 if value > 165 else 0)


def run(page: fitz.Page, dpi: int, preprocess: bool, psm: int) -> str:
    image = render(page, dpi, preprocess)
    return pytesseract.image_to_string(image, lang="chi_sim+eng", config=f"--psm {psm}")


def report(label: str, text: str) -> None:
    cjk = len(CJK_PATTERN.findall(text))
    headings = [line.strip() for line in text.splitlines() if line.strip() and HEADING_HINT.match(line.strip())]
    markers = [marker for marker in ("（一）", "(一)", "（二）", "(二)", "（三）", "(三)", "（四）", "(四)") if marker in text]
    print(f"  [{label}] cjk={cjk} heading_like={len(headings)} markers={markers}")
    for line in headings[:8]:
        print(f"      · {line[:44]}")


def main() -> int:
    if len(sys.argv) < 4:
        raise SystemExit("usage: ocr_quality_probe.py <document-id> <first-page> <last-page>")
    document_path = next(iter(sorted(UPLOAD_DIR.glob(f"{sys.argv[1]}.*"))), None)
    if document_path is None:
        raise SystemExit(f"no uploaded file found for {sys.argv[1]}")
    first_page, last_page = int(sys.argv[2]), int(sys.argv[3])

    configs = (
        ("dpi200 raw psm3", 200, False, 3),
        ("dpi300 raw psm3", 300, False, 3),
        ("dpi300 binary psm3", 300, True, 3),
        ("dpi300 binary psm6", 300, True, 6),
    )

    with fitz.open(document_path) as document:
        print(f"file: {document_path.name} pages={document.page_count}")
        for page_number in range(first_page, min(last_page, document.page_count) + 1):
            print(f"\n=== page {page_number} ===")
            page = document[page_number - 1]
            for label, dpi, preprocess, psm in configs:
                report(label, run(page, dpi, preprocess, psm))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
