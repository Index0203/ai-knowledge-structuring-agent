"""Extractive answer used when no chat model is configured.

The fallback never writes new sentences: it returns verbatim quotes from the
retrieved content blocks so the UI can still show a grounded, cited answer.
"""

import re
from uuid import UUID

from app.agents.node_qa.contracts import EvidenceItem, NodeAnswerResult

MAX_ANSWER_CHARACTERS = 600


def build_extractive_answer(evidence: list[EvidenceItem]) -> NodeAnswerResult:
    if not evidence:
        return NodeAnswerResult(
            answer=None,
            refused=True,
            refusal_reason="No content block in this document matched the question.",
        )

    used_ids: list[UUID] = []
    quotes: list[str] = []
    remaining = MAX_ANSWER_CHARACTERS
    for item in evidence:
        if remaining <= 0:
            break
        excerpt = _first_sentences(item.text, remaining)
        if not excerpt:
            continue
        # Sentence boundaries can overshoot the budget; keep the answer inside it.
        excerpt = excerpt[:remaining].strip()
        if not excerpt:
            continue
        quotes.append(excerpt)
        used_ids.append(item.chunk_id)
        remaining -= len(excerpt)

    if not quotes:
        return NodeAnswerResult(
            answer=None,
            refused=True,
            refusal_reason="The retrieved content blocks contained no quotable text.",
        )

    return NodeAnswerResult(
        answer="\n\n".join(quotes),
        cited_chunk_ids=tuple(used_ids),
        confidence=min(0.5, evidence[0].score),
        refused=False,
    )


def _first_sentences(text: str, budget: int) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    if len(normalized) <= budget:
        return normalized
    sentences = re.split(r"(?<=[.!?。！？])\s*", normalized)
    collected: list[str] = []
    length = 0
    for sentence in sentences:
        if not sentence:
            continue
        if length + len(sentence) > budget and collected:
            break
        collected.append(sentence)
        length += len(sentence)
        if length >= budget:
            break
    excerpt = " ".join(collected).strip()
    if not excerpt:
        return normalized[:budget].strip()
    return excerpt
