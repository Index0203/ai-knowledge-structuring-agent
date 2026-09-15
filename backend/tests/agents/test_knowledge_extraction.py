import pytest
from langchain_core.messages import BaseMessage

from app.agents.knowledge_extraction.agent import KnowledgeExtractionAgent
from app.agents.knowledge_extraction.factory import create_knowledge_extraction_agent
from app.agents.knowledge_extraction.prompts import PROMPT_VERSION
from app.core.config import settings
from app.schemas.documents import DocumentMetadata, DocumentSection, ProcessedDocument, SourceLocation


class FakeStructuredModel:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.messages: list[BaseMessage] = []

    def invoke(self, messages: list[BaseMessage]) -> dict[str, object]:
        self.messages = messages
        return self.response


def make_document() -> ProcessedDocument:
    return ProcessedDocument(
        title="Knowledge Guide",
        sections=[
            DocumentSection(
                title="Introduction",
                level=1,
                text="Knowledge graphs connect concepts with evidence.",
                source_locations=[SourceLocation(paragraph_index=0)],
            )
        ],
        metadata=DocumentMetadata(
            original_filename="guide.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            parser_name="python-docx",
        ),
    )


def test_agent_returns_schema_validated_knowledge_tree() -> None:
    model = FakeStructuredModel(
        {
            "title": "Knowledge Guide",
            "children": [
                {
                    "title": "Knowledge graphs",
                    "summary": "Knowledge graphs connect concepts with evidence.",
                    "keywords": ["knowledge graphs", "evidence"],
                    "source_section_indexes": [0],
                    "children": [],
                }
            ],
        }
    )

    result = KnowledgeExtractionAgent(model).extract(make_document())

    assert result.title == "Knowledge Guide"
    assert result.children[0].keywords == ["knowledge graphs", "evidence"]
    assert PROMPT_VERSION in model.messages[1].content
    assert "untrusted data" in model.messages[0].content


def test_agent_rejects_llm_output_that_does_not_match_schema() -> None:
    model = FakeStructuredModel({"title": "Knowledge Guide", "children": [{"title": "Missing fields"}]})

    with pytest.raises(ValueError):
        KnowledgeExtractionAgent(model).extract(make_document())


def test_production_factory_requires_explicit_llm_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_model", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        create_knowledge_extraction_agent()


def test_production_factory_builds_strict_structured_output_without_request(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "test-model")

    agent = create_knowledge_extraction_agent()

    assert isinstance(agent, KnowledgeExtractionAgent)
