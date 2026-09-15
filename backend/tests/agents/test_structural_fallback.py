import pytest

from app.agents.knowledge_extraction.structural_fallback import build_structural_tree
from app.schemas.documents import DocumentMetadata, DocumentSection, ProcessedDocument, SourceLocation


def make_document(sections: list[tuple[str, int, str]]) -> ProcessedDocument:
    return ProcessedDocument(
        title="专精特新中小企业发展探索",
        sections=[
            DocumentSection(
                title=title,
                level=level,
                text=text,
                source_locations=[SourceLocation(page_number=index + 1)],
            )
            for index, (title, level, text) in enumerate(sections)
        ],
        metadata=DocumentMetadata(
            original_filename="report.pdf",
            media_type="application/pdf",
            parser_name="pymupdf",
        ),
    )


def test_tree_mirrors_the_document_outline() -> None:
    document = make_document(
        [
            ("第二章 数智聚焦", 1, "章节导语"),
            ("一、数字化知识库构建", 2, "构建知识库的具体做法。"),
            ("（一）数据底座", 3, "统一数据标准。"),
            ("第三章 智能工序管控", 1, "本章介绍工序管控。"),
        ]
    )

    tree = build_structural_tree(document)

    assert tree.title == "专精特新中小企业发展探索"
    assert [child.title for child in tree.children] == ["第二章 数智聚焦", "第三章 智能工序管控"]
    chapter = tree.children[0]
    assert [child.title for child in chapter.children] == ["一、数字化知识库构建"]
    assert [child.title for child in chapter.children[0].children] == ["（一）数据底座"]
    assert tree.children[1].children == []


def test_heading_without_body_text_borrows_its_children_evidence() -> None:
    document = make_document(
        [
            ("第二章 数智聚焦", 1, ""),
            ("一、数字化知识库构建", 2, "构建知识库的具体做法。"),
        ]
    )

    tree = build_structural_tree(document)

    chapter = tree.children[0]
    assert chapter.summary == "该章节下含 1 个小节，内容见子节点。"
    assert chapter.source_section_indexes == [0, 1]


def test_tree_requires_extractable_text() -> None:
    document = make_document([])

    with pytest.raises(ValueError, match="no extractable text"):
        build_structural_tree(document)
