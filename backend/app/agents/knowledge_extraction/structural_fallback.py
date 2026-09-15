"""Outline-based knowledge tree used when no chat model is configured.

The tree mirrors the document's own outline: the root is the document title,
its children are the first-level sections, and deeper headings nest underneath.
Every node copies existing text, so the fallback cannot invent content.
"""

from dataclasses import dataclass, field

from app.agents.knowledge_extraction.text_digest import (
    document_term_counts,
    extract_keywords,
    has_content,
    summarize,
)
from app.schemas.documents import DocumentSection, ProcessedDocument
from app.schemas.knowledge_tree import KnowledgeNode, KnowledgeTree

MAX_NODE_CHILDREN = 64
MAX_EVIDENCE_SECTIONS = 24
MAX_KEYWORDS = 5
MAX_KEYWORD_SOURCE_CHARACTERS = 600


@dataclass
class OutlineEntry:
    """One outline node before it is converted to the API schema."""

    section_index: int
    level: int
    title: str
    body: str
    children: list["OutlineEntry"] = field(default_factory=list)

    @property
    def is_structural(self) -> bool:
        return not self.body.strip()

    def section_indexes(self) -> list[int]:
        """Own section plus descendants; used when a heading has no own text."""
        indexes = [self.section_index]
        for child in self.children:
            indexes.extend(child.section_indexes())
        return indexes[:MAX_EVIDENCE_SECTIONS]


def build_structural_tree(document: ProcessedDocument) -> KnowledgeTree:
    entries = _build_outline(document.sections)
    if not entries:
        raise ValueError("Document contains no extractable text.")
    document_counts = document_term_counts(section.text for section in document.sections)
    return KnowledgeTree(
        title=document.title,
        children=[_to_node(entry, document_counts) for entry in entries],
    )


def _build_outline(sections: list[DocumentSection]) -> list[OutlineEntry]:
    roots: list[OutlineEntry] = []
    stack: list[OutlineEntry] = []
    for section_index, section in enumerate(sections):
        entry = OutlineEntry(
            section_index=section_index,
            level=max(1, section.level),
            title=section.title.strip()[:160] or f"Section {section_index + 1}",
            body=section.text,
        )
        while stack and stack[-1].level >= entry.level:
            stack.pop()
        if stack:
            stack[-1].children.append(entry)
        else:
            roots.append(entry)
        stack.append(entry)
    return _limit_children(roots)


def _limit_children(entries: list[OutlineEntry]) -> list[OutlineEntry]:
    for entry in entries:
        entry.children = _limit_children(entry.children[:MAX_NODE_CHILDREN])
    return entries


def _to_node(entry: OutlineEntry, document_counts) -> KnowledgeNode:
    return KnowledgeNode(
        title=entry.title,
        summary=_summary(entry),
        keywords=_keywords(entry, document_counts),
        source_section_indexes=entry.section_indexes(),
        children=[_to_node(child, document_counts) for child in entry.children],
    )


def _summary(entry: OutlineEntry) -> str:
    if has_content(entry.body):
        digest = summarize(" ".join(entry.body.split()))
        if digest:
            return digest
    if entry.children:
        return f"该章节下含 {len(entry.children)} 个小节，内容见子节点。"
    return entry.title


def _keywords(entry: OutlineEntry, document_counts) -> list[str]:
    """Keywords come from the section text, or from its children when it is a heading only."""
    source = " ".join(entry.body.split())[:MAX_KEYWORD_SOURCE_CHARACTERS] if has_content(entry.body) else ""
    if not source and entry.children:
        source = " ".join(
            " ".join(child.body.split()) for child in entry.children
        )[:MAX_KEYWORD_SOURCE_CHARACTERS]
    if not source:
        source = entry.title
    return extract_keywords(source, document_counts=document_counts, limit=MAX_KEYWORDS)
