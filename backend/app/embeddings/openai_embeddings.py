from app.core.config import settings


class OpenAIEmbeddingProvider:
    """Thin wrapper around an OpenAI-compatible embeddings endpoint."""

    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        from langchain_openai import OpenAIEmbeddings

        self.name = model
        self._client = OpenAIEmbeddings(
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=settings.llm_request_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self.dimensions = len(self._client.embed_query("dimension probe"))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._client.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._client.embed_query(text)


def create_openai_embedding_provider() -> OpenAIEmbeddingProvider:
    if not settings.openai_api_key or not settings.openai_embedding_model:
        raise RuntimeError(
            "OPENAI_API_KEY and OPENAI_EMBEDDING_MODEL must be configured for EMBEDDING_PROVIDER=openai."
        )
    return OpenAIEmbeddingProvider(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )
