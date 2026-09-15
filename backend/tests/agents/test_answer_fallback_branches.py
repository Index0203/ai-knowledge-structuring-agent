"""Fallback answer branches and the quiz-payload round trip."""

from uuid import UUID

from app.agents.node_qa.contracts import EvidenceItem
from app.agents.node_qa.fallback import build_extractive_answer
from app.services.question_service import _payload_citation


def evidence(text: str, score: float = 0.6) -> EvidenceItem:
    return EvidenceItem(
        label="c1",
        chunk_id=UUID(int=1),
        text=text,
        location="p.1",
        section_title="Section",
        score=score,
    )


def test_fallback_shortens_a_very_long_quote() -> None:
    long_text = "这是一个很长的句子，用来验证摘录长度受控。" * 40

    result = build_extractive_answer([evidence(long_text)])

    assert result.refused is False
    assert result.answer is not None
    # The extractive answer must respect its character budget exactly.
    assert len(result.answer) <= 600
    assert long_text.startswith(result.answer[:10])


def test_fallback_skips_evidence_without_quotable_text() -> None:
    result = build_extractive_answer([evidence("   \n  ")])

    assert result.refused is True
    assert result.answer is None
    assert "no quotable text" in (result.refusal_reason or "")


def test_fallback_uses_several_blocks_until_the_budget_is_used() -> None:
    items = [evidence(f"第{index}段证据内容。" * 5, score=0.5) for index in range(1, 6)]

    result = build_extractive_answer(items)

    assert result.refused is False
    assert 1 <= len(result.cited_chunk_ids) <= len(items)
    assert result.confidence == 0.5


def test_payload_citation_falls_back_when_the_chunk_is_gone() -> None:
    payload = {
        "chunk_id": str(UUID(int=7)),
        "quote": "历史引用",
        "section_title": "旧章节",
        "relevance": 0.42,
    }

    citation = _payload_citation(payload, {})

    assert citation.chunk_id == UUID(int=7)
    assert citation.quote == "历史引用"
    assert citation.section_title == "旧章节"
    assert citation.relevance == 0.42
    assert citation.page_number is None


def test_payload_citation_survives_a_broken_id() -> None:
    citation = _payload_citation({"chunk_id": "not-a-uuid", "quote": "x"}, {})

    assert citation.chunk_id == UUID(int=0)
    assert citation.quote == "x"
