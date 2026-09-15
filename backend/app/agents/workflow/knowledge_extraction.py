"""Knowledge Extraction Agent — outline skeleton plus model enrichment, then persistence."""

import logging
from uuid import UUID

from app.agents.knowledge_extraction.enrichment import (
    apply_enrichment,
    collect_targets,
    group_by_top_level,
)
from app.agents.knowledge_extraction.factory import create_node_enrichment_agent
from app.agents.knowledge_extraction.structural_fallback import build_structural_tree
from app.agents.workflow.state import KnowledgeDraft, WorkflowDependencies
from app.core.config import settings
from app.repositories.knowledge import KnowledgeRepository
from app.schemas.documents import ProcessedDocument
from app.schemas.knowledge_tree import KnowledgeNode, KnowledgeTree

logger = logging.getLogger(__name__)

TREE_MODE_LLM = "llm"
TREE_MODE_STRUCTURE = "structure_fallback"


class KnowledgeExtractionAgent:
    """Owns the knowledge structure artifact end to end, including its persistence.

    Persisting here means downstream agents (Visualization) work on stored nodes with
    real ids instead of an in-memory tree.
    """

    def __init__(self, enrichment_agent_factory=create_node_enrichment_agent) -> None:
        self._enrichment_agent_factory = enrichment_agent_factory

    def extract(
        self,
        deps: WorkflowDependencies,
        document_id: UUID,
        document: ProcessedDocument,
    ) -> tuple[KnowledgeTree, KnowledgeDraft, UUID]:
        self._ensure_chunks(deps, document_id, document)
        tree = build_structural_tree(document)
        mode = TREE_MODE_STRUCTURE
        if settings.chat_model_configured:
            tree, mode = self._enrich(tree, document)

        repository = KnowledgeRepository(deps.session)
        section_chunk_ids = self._section_chunk_ids(deps, document_id)
        root_id = repository.replace_document_tree(
            document_id=document_id,
            document_title=document.title,
            tree=tree,
            section_chunk_ids=section_chunk_ids,
        )
        deps.session.flush()
        return tree, _describe(tree, mode), root_id

    def _enrich(self, tree: KnowledgeTree, document: ProcessedDocument) -> tuple[KnowledgeTree, str]:
        try:
            agent = self._enrichment_agent_factory()
            targets = collect_targets(tree, document.sections)
            items = {}
            for batch in group_by_top_level(targets):
                items.update(agent.enrich(batch))
            if not items:
                return tree, TREE_MODE_STRUCTURE
            return apply_enrichment(tree, items), TREE_MODE_LLM
        except Exception as error:  # noqa: BLE001 - enrichment must never break the structure
            logger.warning("Node enrichment failed, keeping extractive summaries: %s", error)
            return tree, TREE_MODE_STRUCTURE

    @staticmethod
    def _section_chunk_ids(deps: WorkflowDependencies, document_id: UUID) -> dict[int, list[UUID]]:
        from app.repositories.chunks import ChunkRepository

        return ChunkRepository(deps.session).map_section_indexes_to_chunk_ids(document_id)

    def _ensure_chunks(
        self,
        deps: WorkflowDependencies,
        document_id: UUID,
        document: ProcessedDocument,
    ) -> None:
        """Rebuild the content blocks when they were produced by an older parse."""
        from app.repositories.chunks import ChunkRepository
        from app.services.indexing_service import create_document_indexing_service

        existing = ChunkRepository(deps.session).list_by_document(document_id)
        sections = document.sections
        aligned = bool(existing) and all(
            chunk.section_index < len(sections)
            and chunk.section_title == sections[chunk.section_index].title
            for chunk in existing
        )
        if aligned:
            return
        logger.info("Rebuilding content blocks so node evidence matches the parsed sections.")
        create_document_indexing_service(deps.session).index_processed_document(document_id, document)


def _describe(tree: KnowledgeTree, mode: str) -> KnowledgeDraft:
    labels: list[str] = []
    max_depth = 0
    # The root counts too, so this number matches what the map model reports.
    node_count = 1

    def visit(node: KnowledgeNode, depth: int) -> None:
        nonlocal max_depth, node_count
        node_count += 1
        max_depth = max(max_depth, depth)
        if not node.children and node.title not in labels:
            labels.append(node.title)
        for child in node.children:
            visit(child, depth + 1)

    for child in tree.children:
        visit(child, 1)
    return KnowledgeDraft(mode=mode, node_count=node_count, max_depth=max_depth, labels=labels[:12])
