from langchain_openai import ChatOpenAI

from app.agents.node_qa.agent import NodeQuestionAgent
from app.agents.llm import resolve_structured_output_method
from app.core.config import settings
from app.schemas.answers import AnswerDraft


def create_node_question_agent() -> NodeQuestionAgent:
    """Create the production answering agent with strict structured output."""
    if not settings.openai_api_key or not settings.openai_model:
        raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL must be configured for grounded answering.")

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
        model = chat_model.with_structured_output(AnswerDraft, method="json_schema", strict=True)
    else:
        model = chat_model.with_structured_output(AnswerDraft, method=method)
    return NodeQuestionAgent(model)
