from app.vectorstores import factory
from app.vectorstores.in_memory_vector_store import InMemoryVectorStore


def test_factory_returns_the_chroma_adapter(monkeypatch) -> None:
    store = InMemoryVectorStore()
    monkeypatch.setattr(factory, "create_chroma_vector_store", lambda: store)

    assert factory.create_vector_store() is store
