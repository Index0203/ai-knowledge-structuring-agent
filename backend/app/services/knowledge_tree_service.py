"""Builds the knowledge tree by running the multi-agent workflow, then exposes it."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.knowledge_extraction.factory import create_node_enrichment_agent
from app.agents.workflow.graph import run_workflow
from app.agents.workflow.state import (
    TaskType,
    WorkflowDependencies,
    WorkflowRequest,
    WorkflowStatus,
)
from app.core.config import settings
from app.models.document import TREE_STATUS_BUILDING, TREE_STATUS_FAILED, TREE_STATUS_READY, utc_now
from app.pipelines.document_processing.errors import DocumentProcessingError
from app.pipelines.document_processing.service import (
    DocumentProcessingService,
    create_default_document_processing_service,
)
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge import KnowledgeRepository
from app.schemas.knowledge_tree_api import KnowledgeTreeNodeResponse, KnowledgeTreeResponse

TREE_MODE_LLM = "llm"
TREE_MODE_STRUCTURE = "structure_fallback"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TreeOutcome:
    document_id: UUID
    status: str
    mode: str | None
    node_count: int
    root_node_id: UUID | None = None
    error_message: str | None = None


class KnowledgeTreeService:
    """Owns document-level status transitions; the agents own the artifacts."""

    def __init__(
        self,
        session: Session,
        *,
        processing_service: DocumentProcessingService | None = None,
        enrichment_agent_factory=create_node_enrichment_agent,
    ) -> None:
        self._session = session
        self._processing = processing_service or create_default_document_processing_service()
        self._enrichment_agent_factory = enrichment_agent_factory

    def build(self, document_id: UUID) -> TreeOutcome:
        documents = DocumentRepository(self._session)
        document = documents.get(document_id)
        if document is None:
            raise LookupError(f"Document {document_id} does not exist.")

        document.tree_status = TREE_STATUS_BUILDING
        document.tree_error = None
        self._session.flush()

        try:
            state = run_workflow(
                deps=WorkflowDependencies(
                    session=self._session,
                    upload_dir=settings.upload_dir,
                    processing_service=self._processing,
                    enrichment_agent_factory=self._enrichment_agent_factory,
                ),
                request=WorkflowRequest(task_type=TaskType.BUILD_KNOWLEDGE_MAP, document_id=document.id),
            )
            if state.get("status") == WorkflowStatus.FAILED:
                raise ValueError("; ".join(state.get("errors", [])) or "the knowledge workflow failed")

            knowledge = state["knowledge"]
            _log_journal(logger, document_id, state)
            document.tree_status = TREE_STATUS_READY
            document.tree_mode = knowledge.mode
            document.tree_built_at = utc_now()
            self._session.flush()
            return TreeOutcome(
                document_id=document.id,
                status=TREE_STATUS_READY,
                mode=knowledge.mode,
                node_count=knowledge.node_count,
                root_node_id=state.get("root_node_id"),
            )
        except (DocumentProcessingError, OSError, ValueError, RuntimeError) as error:
            logger.warning("Knowledge workflow failed for %s: %s", document_id, error)
            document.tree_status = TREE_STATUS_FAILED
            document.tree_error = str(error)
            self._session.flush()
            return TreeOutcome(
                document_id=document.id,
                status=TREE_STATUS_FAILED,
                mode=None,
                node_count=0,
                error_message=str(error),
            )


class KnowledgeTreeNotFoundError(Exception):
    """Raised when a document id has no persisted document."""


def _log_journal(logger: logging.Logger, document_id: UUID, state) -> None:
    """Write the agent journal so `docker compose logs worker` explains what ran."""
    plan = state.get("plan")
    if plan is not None:
        logger.info(
            "workflow %s task=%s planned_by=%s steps=%s",
            document_id,
            plan.task_type,
            plan.analysed_by,
            [step.agent for step in plan.steps],
        )
    for trace in state.get("traces", []):
        logger.info(
            "workflow %s agent=%s status=%s used_model=%s duration_ms=%s detail=%s",
            document_id,
            trace.agent,
            trace.status,
            trace.used_model,
            trace.duration_ms,
            trace.detail,
        )


def load_tree_response(session: Session, document_id: UUID) -> KnowledgeTreeResponse:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise KnowledgeTreeNotFoundError(f"Document {document_id} does not exist.")

    knowledge = KnowledgeRepository(session)
    nodes = knowledge.get_tree_nodes(document_id)
    if not nodes:
        return KnowledgeTreeResponse(
            document_id=document.id,
            status=document.tree_status,
            mode=document.tree_mode,
            error_message=document.tree_error,
            tree=None,
        )

    section_indexes = knowledge.node_section_indexes(document_id)
    children_by_parent: dict[UUID | None, list] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    def build(node) -> KnowledgeTreeNodeResponse:
        return KnowledgeTreeNodeResponse(
            id=node.id,
            title=node.title,
            summary=node.summary,
            keywords=list(node.keywords or []),
            source_section_indexes=section_indexes.get(node.id, []),
            depth=node.depth,
            children=[build(child) for child in children_by_parent.get(node.id, [])],
        )

    root = next((node for node in nodes if node.parent_id is None), None)
    return KnowledgeTreeResponse(
        document_id=document.id,
        status=document.tree_status,
        mode=document.tree_mode,
        error_message=document.tree_error,
        tree=build(root) if root is not None else None,
        map=document.map_model,
    )
