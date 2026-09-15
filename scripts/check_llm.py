"""Verify the configured chat model with one tiny structured call.

Usage (inside the compose network):

    docker compose run --rm --no-deps -v "<repo>/scripts:/scripts:ro" backend python /scripts/check_llm.py
"""

from uuid import uuid4

from app.agents.knowledge_extraction.factory import create_knowledge_extraction_agent
from app.agents.llm import resolve_structured_output_method
from app.agents.node_qa.contracts import EvidenceItem
from app.agents.node_qa.factory import create_node_question_agent
from app.core.config import settings
from app.schemas.documents import DocumentMetadata, DocumentSection, ProcessedDocument, SourceLocation


def main() -> int:
    print("base_url:", settings.openai_base_url or "https://api.openai.com")
    print("model:", settings.openai_model)
    print("structured output:", resolve_structured_output_method())
    print("embedding provider:", settings.embedding_provider)
    if not settings.chat_model_configured:
        print("FAIL: OPENAI_API_KEY / OPENAI_MODEL are empty, the pipeline stays in fallback mode.")
        return 1

    document = ProcessedDocument(
        title="检查文档",
        sections=[
            DocumentSection(
                title="专业化与特色化",
                level=1,
                text=(
                    "专业化是指专注核心业务，提高专业化生产、服务和协作配套的能力。"
                    "特色化是指利用特色资源，采用独特工艺、技术、配方或原料，研制生产具有地方特色的产品。"
                ),
                source_locations=[SourceLocation(page_number=1)],
            )
        ],
        metadata=DocumentMetadata(
            original_filename="check.pdf",
            media_type="application/pdf",
            parser_name="check",
        ),
    )

    try:
        tree = create_knowledge_extraction_agent().extract(document)
    except Exception as error:  # noqa: BLE001 - this command exists to report the failure
        print(f"FAIL: knowledge extraction call failed: {error}")
        return 1
    print("OK tree:", tree.title)
    for child in tree.children:
        print(f"  - {child.title} | {child.summary[:60]} | keywords={child.keywords}")

    try:
        answer = create_node_question_agent().answer(
            question="专业化是指什么？",
            node_title=tree.children[0].title if tree.children else document.title,
            node_summary=tree.children[0].summary if tree.children else document.title,
            evidence=[
                EvidenceItem(
                    label="c1",
                    chunk_id=uuid4(),
                    text=document.sections[0].text,
                    location="p.1",
                    section_title="专业化与特色化",
                    score=0.9,
                )
            ],
        )
    except Exception as error:  # noqa: BLE001 - this command exists to report the failure
        print(f"FAIL: answering call failed: {error}")
        return 1
    print(f"OK answer: refused={answer.refused} citations={len(answer.cited_chunk_ids)}")
    print("  ", (answer.answer or answer.refusal_reason or "")[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
