from langchain_core.messages import BaseMessage
import pytest

from app.agents.knowledge_extraction.enrichment import (
    NodeEnrichmentItem,
    NodeEnrichmentAgent,
    accept_corrected_title,
    apply_enrichment,
    build_enrichment_prompt,
    collect_targets,
    group_by_top_level,
)
from app.agents.knowledge_extraction.factory import create_node_enrichment_agent
from app.agents.knowledge_extraction.structural_fallback import build_structural_tree
from app.core.config import settings
from app.schemas.documents import DocumentMetadata, DocumentSection, ProcessedDocument, SourceLocation


class FakeEnrichmentModel:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[list[BaseMessage]] = []

    def invoke(self, messages: list[BaseMessage]) -> dict[str, object]:
        self.calls.append(messages)
        return self.response


def make_document() -> ProcessedDocument:
    return ProcessedDocument(
        title="专精特新中小企业发展探索",
        sections=[
            DocumentSection(
                title="第一章 时代坐标",
                level=1,
                text="",
                source_locations=[SourceLocation(page_number=4)],
            ),
            DocumentSection(
                title="一、专精特新概念及内涵",
                level=2,
                text="专业化是指专注核心业务，提高专业化生产和服务能力。",
                source_locations=[SourceLocation(page_number=4)],
            ),
            DocumentSection(
                title="二、总体态势",
                level=2,
                text="我国累计培育专精特新中小企业超 14 万家。",
                source_locations=[SourceLocation(page_number=8)],
            ),
            DocumentSection(
                title="第二章 数智聚焦",
                level=1,
                text="",
                source_locations=[SourceLocation(page_number=13)],
            ),
            DocumentSection(
                title="一、数字化知识库构建",
                level=2,
                text="构建知识库沉淀技术资产。",
                source_locations=[SourceLocation(page_number=14)],
            ),
        ],
        metadata=DocumentMetadata(
            original_filename="report.pdf",
            media_type="application/pdf",
            parser_name="pymupdf",
        ),
    )


def test_targets_follow_the_outline_paths() -> None:
    document = make_document()
    tree = build_structural_tree(document)

    targets = collect_targets(tree, document.sections)

    assert [target.node_id for target in targets] == ["0", "0.0", "0.1", "1", "1.0"]
    assert targets[1].text.startswith("专业化是指")
    assert targets[0].text.startswith("专业化是指")  # chapter borrows its children's evidence


def test_batches_are_grouped_per_chapter() -> None:
    document = make_document()
    targets = collect_targets(build_structural_tree(document), document.sections)

    batches = group_by_top_level(targets)

    assert [sorted(target.node_id for target in batch) for batch in batches] == [
        ["0", "0.0", "0.1"],
        ["1", "1.0"],
    ]


def test_agent_accepts_known_nodes_and_ignores_invented_ids() -> None:
    document = make_document()
    targets = collect_targets(build_structural_tree(document), document.sections)
    model = FakeEnrichmentModel(
        {
            "items": [
                {"node_id": "0.0", "summary": "专业化强调专注核心业务。", "keywords": ["专业化", "核心业务"]},
                {"node_id": "9.9", "summary": "不该出现。", "keywords": []},
            ]
        }
    )

    result = NodeEnrichmentAgent(model).enrich(targets)

    assert set(result) == {"0.0"}
    assert result["0.0"].keywords == ["专业化", "核心业务"]
    assert "node_id=0.0" in model.calls[0][1].content
    assert "untrusted data" in model.calls[0][0].content


def test_apply_enrichment_keeps_unmentioned_nodes_extractive() -> None:
    document = make_document()
    tree = build_structural_tree(document)
    items = {"0.0": NodeEnrichmentItem(node_id="0.0", summary="模型概括的一句话。", keywords=["专业化"])}

    enriched = apply_enrichment(tree, items)

    assert enriched.children[0].children[0].summary == "模型概括的一句话。"
    assert enriched.children[0].children[0].keywords == ["专业化"]
    # Untouched nodes keep the extractive wording.
    assert "14 万家" in enriched.children[0].children[1].summary
    assert enriched.children[1].children[0].summary != ""


def test_prompt_lists_every_requested_node() -> None:
    document = make_document()
    targets = collect_targets(build_structural_tree(document), document.sections)

    prompt = build_enrichment_prompt(targets)

    assert "node_id=0.1" in prompt
    assert "node-enrichment-v1" in prompt


def test_factory_requires_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_model", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_node_enrichment_agent()


def test_only_plausible_title_repairs_are_accepted() -> None:
    assert accept_corrected_title("一、专精特新概念及内洒", "一、专精特新概念及内涵") == "一、专精特新概念及内涵"
    # A different numbering or an unrelated sentence must never replace the heading.
    assert accept_corrected_title("一、专精特新概念及内洒", "二、专精特新概念及内涵") is None
    assert accept_corrected_title("一、专精特新概念及内洒", "这是一句完全无关的正文。") is None
    assert accept_corrected_title("一、专精特新概念及内洒", None) is None
    assert accept_corrected_title("一、专精特新概念及内洒", "一、专精特新概念及内洒") is None


def test_extra_model_fields_are_ignored_not_fatal() -> None:
    document = make_document()
    targets = collect_targets(build_structural_tree(document), document.sections)
    model = FakeEnrichmentModel(
        {
            "items": [
                {
                    "node_id": "0.0",
                    "summary": "专业化强调专注核心业务。",
                    "keywords": ["专业化"],
                    "reasoning": "the provider added this field",
                    "confidence": 0.9,
                }
            ],
            "usage": {"total_tokens": 42},
        }
    )

    result = NodeEnrichmentAgent(model).enrich(targets)

    assert set(result) == {"0.0"}


def test_enrichment_applies_a_repaired_title() -> None:
    document = make_document()
    tree = build_structural_tree(document)
    # Pretend the parser produced an OCR-damaged title.
    damaged = tree.children[0].children[0].model_copy(update={"title": "一、专精特新概念及内洒"})
    tree = tree.model_copy(
        update={"children": [tree.children[0].model_copy(update={"children": [damaged, tree.children[0].children[1]]}), tree.children[1]]}
    )
    items = {
        "0.0": NodeEnrichmentItem(
            node_id="0.0",
            summary="本章阐释专精特新概念内涵。",
            keywords=["专精特新"],
            corrected_title="一、专精特新概念及内涵",
        )
    }

    enriched = apply_enrichment(tree, items)

    assert enriched.children[0].children[0].title == "一、专精特新概念及内涵"
