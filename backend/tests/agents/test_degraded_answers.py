"""Degraded-mode behaviour when no chat model is configured."""

from uuid import UUID

from app.agents.node_qa.context import build_node_context
from app.agents.node_qa.contracts import EvidenceItem
from app.agents.node_qa.degraded import build_degraded_answer
from app.agents.node_qa.intents import NodeIntent

CHUNK_ID = UUID("cccccccc-0000-0000-0000-000000000001")


def context_with_children() -> object:
    return build_node_context(
        document_title="Handbook",
        node_title="一、数字化知识库构建",
        node_summary="构建知识库沉淀技术资产。",
        keywords=["知识库"],
        children=[("(1) 知识传承", "技术经验依附个体"), ("(2) 技术优化", "迭代效率低")],
        evidence=[
            EvidenceItem(
                label="c1",
                chunk_id=CHUNK_ID,
                text="构建知识库沉淀技术资产。",
                location="p.14",
                section_title="数字化知识库构建",
                score=0.7,
            )
        ],
    )


def test_degraded_explain_quotes_the_evidence() -> None:
    result = build_degraded_answer(context_with_children(), NodeIntent.EXPLAIN)

    assert result.refused is False
    assert result.answer == "构建知识库沉淀技术资产。"
    assert result.cited_chunk_ids == (CHUNK_ID,)


def test_degraded_quiz_uses_child_nodes_and_keeps_citations() -> None:
    result = build_degraded_answer(context_with_children(), NodeIntent.QUIZ)

    assert result.refused is False
    assert len(result.quiz_items) == 2
    assert result.quiz_items[0].question == "请说明「(1) 知识传承」的含义及其作用。"
    assert result.quiz_items[0].answer == "技术经验依附个体"
    assert all(item.cited_chunk_ids == (CHUNK_ID,) for item in result.quiz_items)


def test_degraded_quiz_without_children_asks_about_the_node_itself() -> None:
    context = build_node_context(
        document_title="Handbook",
        node_title="Citations",
        node_summary="引用要求",
        evidence=[
            EvidenceItem(
                label="c1",
                chunk_id=CHUNK_ID,
                text="Every answer must cite its source.",
                location="p.1",
                section_title="Citations",
                score=0.6,
            )
        ],
    )

    result = build_degraded_answer(context, NodeIntent.QUIZ)

    assert len(result.quiz_items) == 1
    assert result.quiz_items[0].question == "请用自己的话解释「Citations」。"
    assert result.quiz_items[0].answer == "引用要求"
