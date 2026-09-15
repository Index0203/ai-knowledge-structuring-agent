from uuid import UUID

from app.agents.node_qa.context import build_node_context
from app.agents.node_qa.contracts import EvidenceItem


def make_evidence(count: int, characters: int = 200) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            label=f"c{index}",
            chunk_id=UUID(int=index),
            text="x" * characters,
            location=f"p.{index}",
            section_title=f"Section {index}",
            score=0.5,
        )
        for index in range(1, count + 1)
    ]


def test_context_is_bounded_and_reports_what_it_dropped() -> None:
    context = build_node_context(
        document_title="Report",
        node_title="Node",
        node_summary="Summary",
        evidence=make_evidence(6),
        max_characters=700,
    )

    assert len(context.evidence) < 6
    assert context.truncated is True
    assert context.dropped_evidence > 0
    assert "Context truncated" in context.render()


def test_context_keeps_child_and_sibling_limits() -> None:
    context = build_node_context(
        document_title="Report",
        node_title="Node",
        node_summary="Summary",
        children=[(f"child {index}", "summary") for index in range(12)],
        siblings=[f"sibling {index}" for index in range(12)],
        evidence=make_evidence(1),
    )

    assert len(context.children) == 8
    assert context.dropped_children == 4
    assert len(context.siblings) == 6


def test_context_without_evidence_is_empty() -> None:
    context = build_node_context(document_title="Report", node_title="Node", node_summary="")

    assert context.is_empty() is True
