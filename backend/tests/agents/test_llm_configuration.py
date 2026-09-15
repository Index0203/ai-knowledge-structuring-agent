from app.agents.knowledge_extraction.factory import create_knowledge_extraction_agent
from app.agents.llm import resolve_structured_output_method
from app.agents.node_qa.factory import create_node_question_agent
from app.core.config import settings


def test_openai_uses_strict_json_schema(monkeypatch) -> None:
    monkeypatch.setattr(settings, "structured_output_method", "auto")
    monkeypatch.setattr(settings, "openai_base_url", None)

    assert resolve_structured_output_method() == "json_schema"


def test_openai_compatible_providers_use_function_calling(monkeypatch) -> None:
    monkeypatch.setattr(settings, "structured_output_method", "auto")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.deepseek.com")

    assert resolve_structured_output_method() == "function_calling"


def test_explicit_method_wins(monkeypatch) -> None:
    monkeypatch.setattr(settings, "structured_output_method", "json_mode")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.deepseek.com")

    assert resolve_structured_output_method() == "json_mode"


def test_factories_build_against_a_deepseek_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(settings, "structured_output_method", "auto")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_model", "deepseek-chat")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.deepseek.com")

    assert create_knowledge_extraction_agent() is not None
    assert create_node_question_agent() is not None
