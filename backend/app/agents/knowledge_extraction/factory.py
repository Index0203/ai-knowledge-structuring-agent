from langchain_openai import ChatOpenAI

from app.agents.knowledge_extraction.agent import KnowledgeExtractionAgent
from app.agents.knowledge_extraction.enrichment import NodeEnrichmentAgent, NodeEnrichmentBatch
from app.agents.llm import resolve_structured_output_method
from app.core.config import settings
from app.schemas.knowledge_tree import KnowledgeTree


def create_knowledge_extraction_agent() -> KnowledgeExtractionAgent:
    """Create the production agent with provider-level strict JSON-schema output."""
    if not settings.openai_api_key or not settings.openai_model:
        raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL must be configured for knowledge extraction.")

    chat_model = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        temperature=0,
        timeout=settings.llm_request_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    method = resolve_structured_output_method()
    if method == "json_schema":
        model = chat_model.with_structured_output(KnowledgeTree, method="json_schema", strict=True)
    else:
        model = chat_model.with_structured_output(KnowledgeTree, method=method)
    return KnowledgeExtractionAgent(model)


def create_node_enrichment_agent() -> NodeEnrichmentAgent:
    """Create the agent that rewrites node summaries and keywords."""
    if not settings.openai_api_key or not settings.openai_model:
        raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL must be configured for node enrichment.")

    chat_model = ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        temperature=0,
        timeout=settings.llm_request_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    method = resolve_structured_output_method()
    if method == "json_schema":
        structured = chat_model.with_structured_output(NodeEnrichmentBatch, method="json_schema", strict=True)
    else:
        structured = chat_model.with_structured_output(NodeEnrichmentBatch, method=method)
    return NodeEnrichmentAgent(structured)
