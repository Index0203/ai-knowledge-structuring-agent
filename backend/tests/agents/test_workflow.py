from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.agents.workflow.graph import run_workflow
from app.agents.workflow.planner import PlannerAgent
from app.agents.workflow.state import (
    AgentName,
    TaskType,
    WorkflowDependencies,
    WorkflowRequest,
    WorkflowStatus,
)
from app.core.config import settings
from app.models.document import Document
from app.vectorstores.in_memory_vector_store import InMemoryVectorStore
from tests.workflow_helpers import prepare_indexed_document

def deps_for(session: Session, tmp_path: Path, store: InMemoryVectorStore) -> WorkflowDependencies:
    return WorkflowDependencies(session=session, upload_dir=str(tmp_path), metadata={"store": store})


# ------------------------------------------------------------------ planner


def test_planner_routes_a_document_request_to_the_knowledge_map_route() -> None:
    plan = PlannerAgent().plan(WorkflowRequest(document_id=UUID(int=1)))

    assert plan.task_type == TaskType.BUILD_KNOWLEDGE_MAP
    assert [step.agent for step in plan.steps] == [
        AgentName.DOCUMENT_ANALYST,
        AgentName.KNOWLEDGE_EXTRACTION,
        AgentName.VISUALIZATION,
    ]
    assert plan.analysed_by == "rules"


def test_planner_routes_a_node_request_to_the_tutor() -> None:
    plan = PlannerAgent().plan(WorkflowRequest(node_id=UUID(int=2), node_intent="quiz"))

    assert plan.task_type == TaskType.TEACH_NODE
    assert [step.agent for step in plan.steps] == [AgentName.TUTOR]


def test_planner_respects_an_explicit_task_type() -> None:
    plan = PlannerAgent().plan(
        WorkflowRequest(task_type=TaskType.ANALYZE_DOCUMENT, document_id=UUID(int=1))
    )

    assert plan.task_type == TaskType.ANALYZE_DOCUMENT
    assert [step.agent for step in plan.steps] == [AgentName.DOCUMENT_ANALYST]


def test_planner_needs_something_to_work_with() -> None:
    with pytest.raises(ValueError, match="document id"):
        PlannerAgent().plan(WorkflowRequest())


# ----------------------------------------------------------------- workflow


def test_analyze_document_only_runs_the_analyst(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    document_id, store, _provider = prepare_indexed_document(session_factory, tmp_path, monkeypatch)

    with session_factory() as session:
        state = run_workflow(
            deps=deps_for(session, tmp_path, store),
            request=WorkflowRequest(task_type=TaskType.ANALYZE_DOCUMENT, document_id=document_id),
        )

    assert state["status"] == WorkflowStatus.SUCCEEDED
    assert state["digest"].section_count == 2
    assert state["digest"].title == "Evidence Handbook"
    assert "tree" not in state
    assert [trace.agent for trace in state["traces"]] == [AgentName.PLANNER, AgentName.DOCUMENT_ANALYST]


def test_build_knowledge_map_runs_analyst_extraction_and_visualization(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    document_id, store, _provider = prepare_indexed_document(session_factory, tmp_path, monkeypatch)

    with session_factory() as session:
        state = run_workflow(
            deps=deps_for(session, tmp_path, store),
            request=WorkflowRequest(task_type=TaskType.BUILD_KNOWLEDGE_MAP, document_id=document_id),
        )
        session.commit()

    assert state["status"] == WorkflowStatus.SUCCEEDED
    assert [trace.agent for trace in state["traces"]] == [
        AgentName.PLANNER,
        AgentName.DOCUMENT_ANALYST,
        AgentName.KNOWLEDGE_EXTRACTION,
        AgentName.VISUALIZATION,
    ]
    knowledge = state["knowledge"]
    assert knowledge.node_count == 3
    assert knowledge.max_depth == 2
    assert knowledge.mode == "structure_fallback"  # no chat model in tests

    map_model = state["map_model"]
    assert map_model.title == "Evidence Handbook"
    assert map_model.root.title == "Evidence Handbook"
    assert map_model.chapter_count == 1
    assert map_model.node_count == knowledge.node_count
    assert map_model.nodes_without_evidence == 0
    assert map_model.edges
    assert map_model.edges[0].source == ""


def test_workflow_persists_the_tree_and_the_map_model(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    document_id, store, _provider = prepare_indexed_document(session_factory, tmp_path, monkeypatch)

    with session_factory() as session:
        run_workflow(
            deps=deps_for(session, tmp_path, store),
            request=WorkflowRequest(task_type=TaskType.BUILD_KNOWLEDGE_MAP, document_id=document_id),
        )
        session.commit()

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document is not None
        assert document.map_model is not None
        assert document.map_model["schema_version"] == "knowledge-map-v1"


def test_stale_chunks_are_rebuilt_before_the_tree_is_built(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    """A parse that changed shape must not leave node evidence pointing at old sections."""
    document_id, store, _provider = prepare_indexed_document(session_factory, tmp_path, monkeypatch)

    with session_factory() as session:
        from sqlalchemy import select

        from app.models.chunk import ContentChunk

        # Simulate chunks produced by an older parser: same count, wrong section titles.
        chunks = session.execute(select(ContentChunk)).scalars().all()
        assert chunks
        for chunk in chunks:
            chunk.section_title = "Page 1"
        session.commit()

    with session_factory() as session:
        state = run_workflow(
            deps=deps_for(session, tmp_path, store),
            request=WorkflowRequest(task_type=TaskType.BUILD_KNOWLEDGE_MAP, document_id=document_id),
        )
        session.commit()

    assert state["map_model"].nodes_without_evidence == 0

    with session_factory() as session:
        from sqlalchemy import select

        from app.models.chunk import ContentChunk

        titles = {chunk.section_title for chunk in session.execute(select(ContentChunk)).scalars().all()}
        assert titles != {"Page 1"}


def test_teach_node_returns_a_tutor_reply_with_citations(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    document_id, store, provider = prepare_indexed_document(session_factory, tmp_path, monkeypatch)

    with session_factory() as session:
        build = run_workflow(
            deps=deps_for(session, tmp_path, store),
            request=WorkflowRequest(task_type=TaskType.BUILD_KNOWLEDGE_MAP, document_id=document_id),
        )
        session.commit()

    from app.repositories.knowledge import KnowledgeRepository
    from app.retrieval.retriever import Retriever

    with session_factory() as session:
        root = build["map_model"].root
        node_id = root.children[0].id
        deps = deps_for(session, tmp_path, store)
        state = run_workflow(
            deps=WorkflowDependencies(
                session=session,
                upload_dir=str(tmp_path),
                retriever=Retriever(session, provider, store),
            ),
            request=WorkflowRequest(
                task_type=TaskType.TEACH_NODE,
                document_id=document_id,
                node_id=node_id,
                node_intent="explain",
            ),
        )

    reply = state["tutor"]
    assert state["status"] == WorkflowStatus.SUCCEEDED
    assert reply.intent == "explain"
    assert reply.mode == "extractive_fallback"
    assert reply.refused is False
    assert reply.citations
    assert [trace.agent for trace in state["traces"]] == [AgentName.PLANNER, AgentName.TUTOR]


def test_workflow_stops_when_an_agent_fails(session_factory, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    with session_factory() as session:
        state = run_workflow(
            deps=WorkflowDependencies(session=session, upload_dir=str(tmp_path)),
            request=WorkflowRequest(task_type=TaskType.BUILD_KNOWLEDGE_MAP, document_id=uuid4()),
        )

    assert state["status"] == WorkflowStatus.FAILED
    assert state["errors"]
    # The workflow stops at the failing agent instead of running the remaining steps.
    assert [trace.agent for trace in state["traces"]] == [AgentName.PLANNER, AgentName.DOCUMENT_ANALYST]
    assert state["traces"][-1].status == "failed"
