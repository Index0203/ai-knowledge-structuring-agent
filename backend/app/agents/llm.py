"""Shared helpers for talking to OpenAI-compatible chat providers."""

from app.core.config import settings

OPENAI_HOST = "api.openai.com"


def resolve_structured_output_method() -> str:
    """Pick a structured-output strategy that the configured provider supports.

    Only OpenAI implements strict `json_schema` responses today; DeepSeek and most
    OpenAI-compatible gateways need function calling instead.
    """
    configured = settings.structured_output_method.strip().lower()
    if configured and configured != "auto":
        return configured
    base_url = (settings.openai_base_url or "").lower()
    if not base_url or OPENAI_HOST in base_url:
        return "json_schema"
    return "function_calling"
