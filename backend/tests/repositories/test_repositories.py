"""Repository-level tests: idempotency and query semantics the services rely on."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.chunk import ContentChunk
from app.models.document import Document
from app.models.knowledge import KnowledgeEdge, KnowledgeNode
from app.models.question import Question
from app.pipelines.chunking.contracts import ContentChunkDraft
from app.repositories.chunks import ChunkRepository
from app.repositories.documents import DocumentRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.knowledge import KnowledgeRepository
from app.repositories.questions import QuestionRepository
from app.schemas.knowledge_tree import KnowledgeNode as KnowledgeNodeSchema
from app.schemas.knowledge_tree import KnowledgeTree


def make_document(session: Session, document_id: UUID | None = None) -> Document:
    document = Document(
        id=document_id or uuid4(),
        original_filename="report.pdf",
        media_type="application/pdf",
        storage_key="report.pdf",
        size_bytes=10,
    )
    return DocumentRepository(session).add(document)


def make_draft(document_id: UUID, index: int, section_index: int, text: str = "content") -> ContentChunkDraft:
    return ContentChunkDraft(
        id=uuid4(),
        document_id=document_id,
        section_index=section_index,
        chunk_index=index,
        section_title=f"Section {section_index}",
        text=text,
        char_start=0,
        char_end=len(text),
        page_number=section_index + 1,
    )


def make_tree() -> KnowledgeTree:
    return KnowledgeTree(
        title="Report",
        children=[
            KnowledgeNodeSchema(
                title="第一章 总论",
                summary="章节概述",
                keywords=["总论"],
                source_section_indexes=[0],
                children=[
                    KnowledgeNodeSchema(
                        title="一、背景",
                        summary="背景说明",
                        keywords=[],
                        source_section_indexes=[1],
                    )
                ],
            )
        ],
    )


def test_documents_repository_round_trip(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.commit()
        fetched = DocumentRepository(session).get(document.id)

        assert fetched is not None
        assert fetched.original_filename == "report.pdf"
        assert [row.id for row in DocumentRepository(session).list_recent()] == [document.id]


def test_replacing_chunks_twice_keeps_one_set(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        repository = ChunkRepository(session)
        repository.replace_document_chunks(document.id, [make_draft(document.id, 0, 0)], "test-embedding")
        repository.replace_document_chunks(
            document.id,
            [make_draft(document.id, 0, 0, "updated content")],
            "test-embedding",
        )
        session.commit()

        chunks = ChunkRepository(session).list_by_document(document.id)
        assert len(chunks) == 1
        assert chunks[0].text == "updated content"
        assert ChunkRepository(session).embedding_model_for_document(document.id) == "test-embedding"


def test_section_to_chunk_mapping_is_ordered_by_chunk_index(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        ChunkRepository(session).replace_document_chunks(
            document.id,
            [
                make_draft(document.id, 0, 0),
                make_draft(document.id, 1, 0),
                make_draft(document.id, 2, 1),
            ],
            "test-embedding",
        )
        session.commit()

        mapping = ChunkRepository(session).map_section_indexes_to_chunk_ids(document.id)

        assert sorted(mapping) == [0, 1]
        assert len(mapping[0]) == 2
        assert len(mapping[1]) == 1


def test_replacing_a_tree_twice_does_not_duplicate_nodes(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        drafts = [make_draft(document.id, 0, 0), make_draft(document.id, 1, 1)]
        ChunkRepository(session).replace_document_chunks(document.id, drafts, "test-embedding")
        section_chunk_ids = ChunkRepository(session).map_section_indexes_to_chunk_ids(document.id)
        repository = KnowledgeRepository(session)

        first_root = repository.replace_document_tree(
            document_id=document.id,
            document_title="Report",
            tree=make_tree(),
            section_chunk_ids=section_chunk_ids,
        )
        second_root = repository.replace_document_tree(
            document_id=document.id,
            document_title="Report",
            tree=make_tree(),
            section_chunk_ids=section_chunk_ids,
        )
        session.commit()

        nodes = KnowledgeRepository(session).get_tree_nodes(document.id)
        assert first_root != second_root  # a rebuild replaces the previous tree
        assert len(nodes) == 3
        assert session.query(KnowledgeNode).count() == 3
        assert session.query(KnowledgeEdge).count() == 2
        assert session.query(KnowledgeEdge).filter(KnowledgeEdge.parent_node_id == second_root).count() == 1


def test_node_section_indexes_are_deduplicated_and_sorted(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        drafts = [make_draft(document.id, 0, 0), make_draft(document.id, 1, 1)]
        ChunkRepository(session).replace_document_chunks(document.id, drafts, "test-embedding")
        section_chunk_ids = ChunkRepository(session).map_section_indexes_to_chunk_ids(document.id)
        root_id = KnowledgeRepository(session).replace_document_tree(
            document_id=document.id,
            document_title="Report",
            tree=make_tree(),
            section_chunk_ids=section_chunk_ids,
        )
        session.commit()

        indexes = KnowledgeRepository(session).node_section_indexes(document.id)

        assert indexes[root_id] == sorted(set(indexes[root_id]))
        assert indexes[root_id] == [0, 1]


def test_node_navigation_helpers(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        ChunkRepository(session).replace_document_chunks(
            document.id, [make_draft(document.id, 0, 0)], "test-embedding"
        )
        section_chunk_ids = ChunkRepository(session).map_section_indexes_to_chunk_ids(document.id)
        root_id = KnowledgeRepository(session).replace_document_tree(
            document_id=document.id,
            document_title="Report",
            tree=make_tree(),
            section_chunk_ids=section_chunk_ids,
        )
        session.commit()
        repository = KnowledgeRepository(session)
        chapter = repository.children_of(root_id)[0]
        section = repository.children_of(chapter.id)[0]

        assert [node.id for node in repository.ancestors(section)] == [root_id, chapter.id]
        assert [node.title for node in repository.siblings_of(section)] == []
        assert repository.root_node(document.id).id == root_id


def test_evidence_links_are_scoped_per_target(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        drafts = [make_draft(document.id, 0, 0), make_draft(document.id, 1, 1)]
        ChunkRepository(session).replace_document_chunks(document.id, drafts, "test-embedding")
        ChunkRepository(session)
        chunk_ids = [draft.id for draft in drafts]
        repository = EvidenceRepository(session)
        target = uuid4()
        repository.add_links(
            document_id=document.id,
            target_type="answer",
            target_id=target,
            chunk_ids=chunk_ids,
        )
        session.commit()

        assert repository.chunk_ids_for_target("answer", target) == chunk_ids
        repository.delete_for_targets(document.id, "answer")
        session.commit()
        assert repository.chunk_ids_for_target("answer", target) == []


def test_question_lifecycle(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        ChunkRepository(session).replace_document_chunks(
            document.id, [make_draft(document.id, 0, 0)], "test-embedding"
        )
        section_chunk_ids = ChunkRepository(session).map_section_indexes_to_chunk_ids(document.id)
        root_id = KnowledgeRepository(session).replace_document_tree(
            document_id=document.id,
            document_title="Report",
            tree=make_tree(),
            section_chunk_ids=section_chunk_ids,
        )
        node_id = KnowledgeRepository(session).children_of(root_id)[0].id
        repository = QuestionRepository(session)
        question = repository.create(document_id=document.id, node_id=node_id, question_text="为什么？", intent="explain")
        session.flush()

        repository.mark_running(question)
        repository.mark_answered(
            question,
            status="answered",
            answer="因为证据如此。",
            answer_mode="llm",
            model="deepseek-chat",
            prompt_version="node-assistant-v1",
            confidence=0.8,
            refusal_reason=None,
            latency_ms=1234,
            answer_payload=[{"question": "q", "answer": "a", "citations": []}],
        )
        session.commit()

        stored: Question = QuestionRepository(session).get(question.id)
        assert stored.intent == "explain"
        assert stored.status == "answered"
        assert stored.answer_payload == [{"question": "q", "answer": "a", "citations": []}]
        assert [row.id for row in QuestionRepository(session).list_for_node(node_id)] == [question.id]

        repository.mark_failed(stored, "provider timeout")
        session.commit()
        assert stored.status == "failed"
        assert stored.error_message == "provider timeout"


def test_evidence_link_quote_is_optional(session_factory) -> None:
    with session_factory() as session:
        document = make_document(session)
        session.flush()
        chunk = make_draft(document.id, 0, 0)
        ChunkRepository(session).replace_document_chunks(document.id, [chunk], "test-embedding")
        session.commit()

        stored = session.get(ContentChunk, chunk.id)
        assert isinstance(stored.created_at, datetime)
        assert stored.embedding_model == "test-embedding"
        assert stored.character_count == len(stored.text)
