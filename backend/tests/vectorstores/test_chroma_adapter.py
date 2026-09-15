"""Contract tests for the ChromaDB adapter, using a fake client (no network)."""

from uuid import uuid4

import pytest

from app.vectorstores.chroma_vector_store import ChromaVectorStore, create_chroma_vector_store
from app.vectorstores.contracts import VectorRecord


class FakeCollection:
    def __init__(self, name: str, metadata: dict | None) -> None:
        self.name = name
        self.metadata = metadata
        self.upserts: list[dict] = []
        self.queries: list[dict] = []
        self.deletes: list[dict] = []
        self.ids_to_return: list[str] = []
        self.distances_to_return: list[float] = []

    def upsert(self, **kwargs) -> None:
        self.upserts.append(kwargs)

    def query(self, **kwargs) -> dict:
        self.queries.append(kwargs)
        return {"ids": [self.ids_to_return], "distances": [self.distances_to_return]}

    def delete(self, where: dict) -> None:
        self.deletes.append(where)


class FakeClient:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.collection = FakeCollection("pending", None)

    def get_or_create_collection(self, name: str, metadata: dict | None = None) -> FakeCollection:
        self.collection.name = name
        self.collection.metadata = metadata
        return self.collection


@pytest.fixture
def store(monkeypatch) -> tuple[ChromaVectorStore, FakeClient]:
    client = FakeClient("chromadb", 8000)
    monkeypatch.setattr("app.vectorstores.chroma_vector_store.chromadb.HttpClient", lambda **kwargs: client)
    return ChromaVectorStore(host="chromadb", port=8000, collection_name="document_chunks"), client


def test_collection_uses_cosine_space(store) -> None:
    _adapter, client = store

    assert client.collection.name == "document_chunks"
    assert client.collection.metadata == {"hnsw:space": "cosine"}


def test_upsert_sends_ids_vectors_metadata_and_documents(store) -> None:
    adapter, client = store
    chunk_id = uuid4()
    document_id = uuid4()
    record = VectorRecord(
        chunk_id=chunk_id,
        document_id=document_id,
        embedding=[0.1, 0.2],
        text="evidence",
        metadata={"document_id": str(document_id), "section_index": 1},
    )

    adapter.upsert([record])

    payload = client.collection.upserts[0]
    assert payload["ids"] == [str(chunk_id)]
    assert payload["embeddings"] == [[0.1, 0.2]]
    assert payload["documents"] == ["evidence"]
    assert payload["metadatas"] == [{"document_id": str(document_id), "section_index": 1}]


def test_upsert_without_records_is_a_noop(store) -> None:
    adapter, client = store

    adapter.upsert([])

    assert client.collection.upserts == []


def test_query_filters_by_document_and_converts_distance_to_score(store) -> None:
    adapter, client = store
    document_id = uuid4()
    chunk_id = uuid4()
    client.collection.ids_to_return = [str(chunk_id)]
    client.collection.distances_to_return = [0.25]

    matches = adapter.query(document_id=document_id, query_embedding=[0.1, 0.2], limit=3)

    request = client.collection.queries[0]
    assert request["where"] == {"document_id": str(document_id)}
    assert request["n_results"] == 3
    assert matches[0].chunk_id == chunk_id
    assert matches[0].score == pytest.approx(0.75)


def test_query_with_a_non_positive_limit_skips_the_backend(store) -> None:
    adapter, client = store

    assert adapter.query(document_id=uuid4(), query_embedding=[0.1], limit=0) == []
    assert client.collection.queries == []


def test_delete_document_scopes_the_filter(store) -> None:
    adapter, client = store
    document_id = uuid4()

    adapter.delete_document(document_id)

    assert client.collection.deletes == [{"document_id": str(document_id)}]


def test_factory_uses_the_configured_collection(monkeypatch, store) -> None:
    _adapter, client = store

    created = create_chroma_vector_store()

    assert created is not None
    assert client.collection.name == "document_chunks"


def test_query_tolerates_an_empty_result(store) -> None:
    adapter, client = store
    client.collection.ids_to_return = []
    client.collection.distances_to_return = []

    assert adapter.query(document_id=uuid4(), query_embedding=[0.1], limit=2) == []
