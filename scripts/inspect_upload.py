"""Diagnostic: report text-layer coverage for the most recent uploaded documents."""

from pathlib import Path

import fitz

UPLOAD_DIR = Path("data/uploads")
SAMPLE_PAGES = 6


def main() -> int:
    uploads = sorted(UPLOAD_DIR.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
    print(f"files in {UPLOAD_DIR}: {len(uploads)}")
    for path in uploads[:5]:
        print(f"  {path.name}  {path.stat().st_size / 1024 / 1024:.2f} MB")
    if not uploads:
        return 1

    target = uploads[0]
    print(f"\ninspecting {target.name}")
    with fitz.open(target) as document:
        print(f"pages: {document.page_count}")
        total_characters = 0
        total_images = 0
        for index, page in enumerate(document):
            text = page.get_text("text").strip()
            images = len(page.get_images(full=True))
            total_characters += len(text)
            total_images += images
            if index < SAMPLE_PAGES:
                print(f"  page {index + 1}: text chars={len(text)} images={images}")
        print(f"total text characters: {total_characters}")
        print(f"total embedded images: {total_images}")
        print(f"text per page: {total_characters / max(document.page_count, 1):.1f} characters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
