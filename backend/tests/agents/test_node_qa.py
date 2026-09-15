from uuid import UUID

import pytest
from langchain_core.messages import BaseMessage

from app.agents.node_qa.agent import NodeQuestionAgent
from app.agents.node_qa.context import build_node_context
from app.agents.node_qa.contracts import EvidenceItem
from app.agents.node_qa.factory import create_node_question_agent
from app.agents.node_qa.fallback import build_extractive_answer
from app.agents.node_qa.intents import NodeIntent
from app.agents.node_qa.prompts import PROMPT_VERSION
from app.core.config import settings

CHUNK_ID = UUID("bbbbbbbb-0000-0000-0000-000000000001")
OTHER_CHUNK_ID = UUID("bbbbbbbb-0000-0000-0000-000000000002")


class FakeDraftModel:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.messages: list[BaseMessage] = []

    def invoke(self, messages: list[BaseMessage]) -> dict[str, object]:
        self.messages = messages
        return self.response


def evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            label="c1",
            chunk_id=CHUNK_ID,
            text="Every answer must cite the content block it came from.",
            location="p.1",
            section_title="Citations",
            score=0.8,
        )
    ]


def context(intent_children: list[tuple[str, str]] | None = None):
    return build_node_context(
        document_title="Evidence Handbook",
        breadcrumb=("第一章 说明",),
        node_title="Citations",
        node_summary="Citation obligations",
        keywords=["citations"],
        children=intent_children or [],
        siblings=["Retrieval"],
        evidence=evidence(),
    )


def test_context_renders_identity_outline_and_labelled_evidence() -> None:
    rendered = context([("Fine print", "Details of the citation rule")]).render()

    assert "Document: Evidence Handbook" in rendered
    assert "Outline path: 第一章 说明" in rendered
    assert "Node: Citations" in rendered
    assert "Child nodes:" in rendered
    assert "Sibling nodes (for contrast): Retrieval" in rendered
    assert "Evidence c1" in rendered


def test_agent_returns_an_answer_bound_to_node_context() -> None:
    model = FakeDraftModel(
        {
            "answer": "Answers must cite their content block.",
            "cited_evidence_ids": ["c1"],
            "confidence": 0.7,
            "insufficient_evidence": False,
        }
    )

    result = NodeQuestionAgent(model).answer(
        context=context(),
        intent=NodeIntent.EXPLAIN,
        question="解释一下",
    )

    assert result.refused is False
    assert result.cited_chunk_ids == (CHUNK_ID,)
    assert PROMPT_VERSION in model.messages[1].content
    assert "Task: explain" in model.messages[1].content
    assert "untrusted data" in model.messages[0].content


def test_agent_uses_the_intent_instruction() -> None:
    model = FakeDraftModel(
        {"answer": "请看示例。", "cited_evidence_ids": ["c1"], "confidence": 0.5, "insufficient_evidence": False}
    )

    NodeQuestionAgent(model).answer(context=context(), intent=NodeIntent.EXAMPLE)

    assert "examples" in model.messages[1].content


def test_non_quiz_intents_drop_volunteered_quiz_items() -> None:
    model = FakeDraftModel(
        {
            "answer": "解释。",
            "cited_evidence_ids": ["c1"],
            "confidence": 0.5,
            "insufficient_evidence": False,
            "quiz_items": [{"question": "q", "answer": "a", "cited_evidence_ids": ["c1"]}],
        }
    )

    result = NodeQuestionAgent(model).answer(context=context(), intent=NodeIntent.EXPLAIN)

    assert result.quiz_items == ()


def test_over_long_model_output_is_trimmed_instead_of_rejected() -> None:
    model = FakeDraftModel(
        {
            "answer": "很长的回答。" * 2000,
            "cited_evidence_ids": ["c1"],
            "confidence": 0.5,
            "insufficient_evidence": False,
        }
    )

    result = NodeQuestionAgent(model).answer(context=context())

    assert result.refused is False
    assert result.answer is not None
    assert len(result.answer) <= 6000


def test_agent_keeps_only_quiz_items_with_valid_citations() -> None:
    model = FakeDraftModel(
        {
            "answer": "3 道自测题",
            "cited_evidence_ids": [],
            "confidence": 0.6,
            "insufficient_evidence": False,
            "quiz_items": [
                {
                    "question": "答案必须做什么？",
                    "answer": "必须引用它来自的内容块。",
                    "cited_evidence_ids": ["c1"],
                },
                {"question": "编造的问题", "answer": "没有引用。", "cited_evidence_ids": ["c99"]},
            ],
        }
    )

    result = NodeQuestionAgent(model).answer(context=context(), intent=NodeIntent.QUIZ)

    assert result.refused is False
    assert len(result.quiz_items) == 1
    assert result.quiz_items[0].cited_chunk_ids == (CHUNK_ID,)


def test_quiz_without_any_valid_citation_is_refused() -> None:
    model = FakeDraftModel(
        {
            "answer": "自测题",
            "cited_evidence_ids": [],
            "confidence": 0.6,
            "insufficient_evidence": False,
            "quiz_items": [{"question": "q", "answer": "a", "cited_evidence_ids": ["c99"]}],
        }
    )

    result = NodeQuestionAgent(model).answer(context=context(), intent=NodeIntent.QUIZ)

    assert result.refused is True
    assert result.answer is None


def test_agent_refuses_an_answer_that_cites_unknown_evidence() -> None:
    model = FakeDraftModel(
        {
            "answer": "Answers must cite their content block.",
            "cited_evidence_ids": ["c99"],
            "confidence": 0.9,
            "insufficient_evidence": False,
        }
    )

    result = NodeQuestionAgent(model).answer(context=context())

    assert result.refused is True
    assert result.answer is None
    assert result.cited_chunk_ids == ()
    assert "traced to any retrieved content block" in (result.refusal_reason or "")


def test_agent_refuses_when_the_model_reports_insufficient_evidence() -> None:
    model = FakeDraftModel(
        {
            "answer": "The evidence is insufficient.",
            "cited_evidence_ids": ["c1"],
            "confidence": 0.2,
            "insufficient_evidence": True,
        }
    )

    result = NodeQuestionAgent(model).answer(context=context())

    assert result.refused is True
    assert result.answer is None


def test_agent_refuses_when_the_node_has_no_evidence() -> None:
    model = FakeDraftModel({"answer": "x", "cited_evidence_ids": [], "confidence": 0.0})
    empty_context = build_node_context(
        document_title="Evidence Handbook",
        node_title="Citations",
        node_summary="",
        evidence=[],
    )

    result = NodeQuestionAgent(model).answer(context=empty_context)

    assert result.refused is True
    assert model.messages == []


def test_extractive_fallback_quotes_the_source_verbatim() -> None:
    result = build_extractive_answer(evidence())

    assert result.refused is False
    assert result.cited_chunk_ids == (CHUNK_ID,)
    assert result.answer == "Every answer must cite the content block it came from."


def test_extractive_fallback_refuses_without_evidence() -> None:
    result = build_extractive_answer([])

    assert result.refused is True
    assert result.answer is None


def test_production_factory_requires_explicit_llm_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_model", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_node_question_agent()


def test_production_factory_builds_a_strict_structured_agent(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "test-model")

    agent = create_node_question_agent()

    assert isinstance(agent, NodeQuestionAgent)
