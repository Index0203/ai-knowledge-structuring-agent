from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings.deterministic import DeterministicEmbeddingProvider
from app.models.chunk import ContentChunk
from app.models.document import Document
from app.retrieval.retriever import SCOPE_NODE_EVIDENCE, Retriever
from app.vectorstores.contracts import VectorRecord
from app.vectorstores.in_memory_vector_store import InMemoryVectorStore

DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
OTHER_DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
CHUNK_A = UUID("aaaaaaaa-0000-0000-0000-000000000001")
CHUNK_B = UUID("aaaaaaaa-0000-0000-0000-000000000002")
CHUNK_C = UUID("aaaaaaaa-0000-0000-0000-000000000003")


def seed_document(session: Session, document_id: UUID) -> None:
    session.add(
        Document(
            id=document_id,
            original_filename="report.pdf",
            media_type="application/pdf",
            storage_key=f"{document_id}.pdf",
            size_bytes=10,
        )
    )


def add_chunk(session: Session, chunk_id: UUID, document_id: UUID, index: int, text: str) -> None:
    session.add(
        ContentChunk(
            id=chunk_id,
            document_id=document_id,
            section_index=index,
            chunk_index=index,
            section_title=f"Section {index}",
            text=text,
            character_count=len(text),
            char_start=0,
            char_end=len(text),
            page_number=index + 1,
            embedding_model="test",
        )
    )


def build_retriever(session: Session) -> tuple[Retriever, InMemoryVectorStore]:
    provider = DeterministicEmbeddingProvider(dimensions=256)
    store = InMemoryVectorStore()
    session.flush()
    for chunk in session.execute(select(ContentChunk)).scalars().all():
        store.upsert(
            [
                VectorRecord(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    embedding=provider.embed_query(chunk.text),
                    text=chunk.text,
                    metadata={"document_id": str(chunk.document_id)},
                )
            ]
        )
    return Retriever(session, provider, store), store


def test_retrieval_is_limited_to_the_requested_document(db_session: Session) -> None:
    seed_document(db_session, DOCUMENT_ID)
    seed_document(db_session, OTHER_DOCUMENT_ID)
    add_chunk(db_session, CHUNK_A, DOCUMENT_ID, 0, "Knowledge graph evidence retrieval")
    add_chunk(db_session, CHUNK_B, OTHER_DOCUMENT_ID, 0, "Knowledge graph evidence retrieval elsewhere")
    retriever, _ = build_retriever(db_session)

    results = retriever.retrieve(
        document_id=DOCUMENT_ID,
        query="knowledge graph evidence",
        min_score=0.0,
    )

    assert [result.chunk_id for result in results] == [CHUNK_A]


def test_node_evidence_is_boosted_and_labelled(db_session: Session) -> None:
    seed_document(db_session, DOCUMENT_ID)
    add_chunk(db_session, CHUNK_A, DOCUMENT_ID, 0, "Knowledge graph evidence retrieval")
    add_chunk(db_session, CHUNK_B, DOCUMENT_ID, 1, "Knowledge graph evidence")
    retriever, _ = build_retriever(db_session)

    results = retriever.retrieve(
        document_id=DOCUMENT_ID,
        query="knowledge graph evidence",
        node_evidence_chunk_ids=frozenset({CHUNK_B}),
        min_score=0.0,
        node_evidence_boost=0.5,
    )

    assert results[0].chunk_id == CHUNK_B
    assert results[0].scope == SCOPE_NODE_EVIDENCE
    assert results[0].location_label == "p.2"


def test_hits_below_the_threshold_are_dropped(db_session: Session) -> None:
    seed_document(db_session, DOCUMENT_ID)
    add_chunk(db_session, CHUNK_A, DOCUMENT_ID, 0, "Knowledge graph evidence retrieval")
    retriever, _ = build_retriever(db_session)

    results = retriever.retrieve(
        document_id=DOCUMENT_ID,
        query="knowledge graph evidence",
        min_score=0.99,
    )

    assert results == []
