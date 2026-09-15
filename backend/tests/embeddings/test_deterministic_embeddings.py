import math

from app.embeddings.deterministic import DeterministicEmbeddingProvider


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_embedding_is_deterministic_and_normalised() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=128)

    first = provider.embed_query("Evidence based retrieval")
    second = provider.embed_query("Evidence based retrieval")

    assert first == second
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0, rel_tol=1e-9)


def test_related_text_scores_higher_than_unrelated_text() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=256)
    query = provider.embed_query("knowledge graph evidence")

    related = provider.embed_query("The knowledge graph connects evidence to nodes.")
    unrelated = provider.embed_query("Quarterly revenue invoice for furniture delivery.")

    assert cosine(query, related) > cosine(query, unrelated)


def test_cjk_text_is_embedded_by_characters_and_bigrams() -> None:
    provider = DeterministicEmbeddingProvider(dimensions=64)

    first = provider.embed_query("知识图谱")
    second = provider.embed_query("知识图谱")
    other = provider.embed_query("财务报表")

    assert first == second
    assert cosine(first, other) < 1.0
