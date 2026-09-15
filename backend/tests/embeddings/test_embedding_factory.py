"""Provider selection for embeddings, including the failure paths."""

import pytest

from app.core.config import settings
from app.embeddings.deterministic import DeterministicEmbeddingProvider
from app.embeddings.factory import create_embedding_provider, describe_embedding_provider


def test_default_provider_is_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "deterministic")
    monkeypatch.setattr(settings, "embedding_dimensions", 32)

    provider = create_embedding_provider()

    assert isinstance(provider, DeterministicEmbeddingProvider)
    assert provider.dimensions == 32
    assert describe_embedding_provider() == "deterministic-hashing-32"


def test_unknown_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "carrier-pigeon")

    with pytest.raises(RuntimeError, match="Unsupported EMBEDDING_PROVIDER"):
        create_embedding_provider()
    assert describe_embedding_provider() == "unsupported:carrier-pigeon"


def test_openai_provider_requires_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_embedding_model", None)

    with pytest.raises(RuntimeError, match="OPENAI_EMBEDDING_MODEL"):
        create_embedding_provider()


def test_openai_provider_description_uses_the_model_name(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_embedding_model", "text-embedding-3-small")

    assert describe_embedding_provider() == "text-embedding-3-small"
