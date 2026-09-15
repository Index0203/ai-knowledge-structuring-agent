"""Diagnostic: show how the PDF parser reads a document's outline."""

import sys
import tempfile
from pathlib import Path

import fitz

from app.pipelines.document_processing.headings import (
    detect_level,
    estimate_body_size,
    extract_lines,
    is_table_of_contents,
)
from app.pipelines.document_processing.parsers.pdf_parser import PdfDocumentParser


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        path = Path(tempfile.mkdtemp()) / "with-toc.pdf"
        document = fitz.open()
        contents = document.new_page()
        contents.insert_text((72, 72), "第一章 总论 ......... 2", fontsize=11)
        contents.insert_text((72, 92), "第二章 方法 ......... 3", fontsize=11)
        contents.insert_text((72, 112), "第三章 结论 ......... 5", fontsize=11)
        body = document.new_page()
        body.insert_text((72, 72), "第一章 总论", fontsize=18)
        body.insert_text((72, 104), "本章讨论总体情况。", fontsize=11)
        body.insert_text((72, 140), "第二章 方法", fontsize=18)
        body.insert_text((72, 172), "本章说明研究方法。", fontsize=11)
        document.save(path)
        document.close()
    elif len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        raise SystemExit("usage: inspect_headings.py <path> | --demo")

    parser = PdfDocumentParser(None)
    with fitz.open(path) as document:
        pages = parser._extract_pages(document)
        for page in pages:
            body_size = estimate_body_size(page.lines)
            print(f"page {page.page_number}: toc={is_table_of_contents(page.lines)} body_size={body_size}")
            for line in page.lines:
                print(f"    size={line.size} level={detect_level(line, body_size)} :: {line.text[:60]}")
        sections, source = parser._build_sections(document, pages)
        print(f"structure_source={source} sections={len(sections)}")
        for section in sections[:10]:
            print(f"  [{section.level}] {section.title} :: {section.text[:40]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
