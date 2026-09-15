"""Diagnostic: show the parser's line list and detected levels for a page.

Usage:
    docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" -e PYTHONPATH=/app \
        backend python /scripts/debug_lines.py
"""

import tempfile
from pathlib import Path

import fitz

from app.pipelines.document_processing.headings import detect_level, split_inline_items
from app.pipelines.document_processing.parsers.pdf_parser import PdfDocumentParser


def build_sample() -> Path:
    path = Path(tempfile.mkdtemp()) / "sample.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 60), "一、数字化知识库构建", fontsize=16, fontname="china-s")
    page.insert_text((72, 90), "本节介绍知识库。", fontsize=11, fontname="china-s")
    page.insert_text(
        (72, 120),
        "传统发展痛点: (1) 知识传承: 技术经验依附个体; (2) 技术优化: 迭代效率低;",
        fontsize=11,
        fontname="china-s",
    )
    page.insert_text((72, 150), "(3) 系统匹配: 通用数字化系统适配不足", fontsize=11, fontname="china-s")
    document.save(path)
    document.close()
    return path


def main() -> int:
    path = build_sample()
    parser = PdfDocumentParser(None)
    with fitz.open(path) as document:
        pages = parser._extract_pages(document)
        for page in pages:
            print(f"page {page.page_number} lines={len(page.lines)}")
            for index, line in enumerate(page.lines):
                print(f"  raw[{index}] level={detect_level(line, None)} :: {line.text}")
                for part in split_inline_items(line.text):
                    print(f"      split -> {part}")
        sections, source = parser._build_sections(document, pages)
        print("structure_source:", source)
        for section in sections:
            print(f"  [{section.level}] {section.title!r} body={section.text[:40]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
