from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers every table before create_all
from app.db.base import Base
from app.db.session import get_session
from app.core.config import settings
from app.embeddings.deterministic import DeterministicEmbeddingProvider
from app.main import app
from app.vectorstores.in_memory_vector_store import InMemoryVectorStore


@pytest.fixture(autouse=True)
def disable_chat_model(monkeypatch) -> None:
    """Tests must never call a paid model, even when .env holds a real key."""
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_model", None)
    monkeypatch.setattr(settings, "openai_base_url", None)


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    """Isolated in-memory database so tests never touch the development data."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    yield factory
    engine.dispose()


@pytest.fixture
def vector_store() -> InMemoryVectorStore:
    """Hermetic vector index: tests never touch ChromaDB."""
    return InMemoryVectorStore()


@pytest.fixture
def embedding_provider() -> DeterministicEmbeddingProvider:
    return DeterministicEmbeddingProvider(dimensions=256)


@pytest.fixture
def db_session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
