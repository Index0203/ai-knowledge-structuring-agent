from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.evidence import EVIDENCE_TARGET_EDGE, EVIDENCE_TARGET_NODE
from app.models.knowledge import KnowledgeEdge, KnowledgeNode
from app.repositories.evidence import MAX_QUOTE_CHARACTERS, EvidenceRepository
from app.schemas.knowledge_tree import KnowledgeNode as KnowledgeNodeSchema
from app.schemas.knowledge_tree import KnowledgeTree

MAX_EVIDENCE_CHUNKS_PER_NODE = 12
MAX_ROOT_EVIDENCE_CHUNKS = 50


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._evidence = EvidenceRepository(session)

    def replace_document_tree(
        self,
        *,
        document_id: UUID,
        document_title: str,
        tree: KnowledgeTree,
        section_chunk_ids: dict[int, list[UUID]],
    ) -> UUID:
        self._evidence.delete_for_targets(document_id, EVIDENCE_TARGET_NODE)
        self._evidence.delete_for_targets(document_id, EVIDENCE_TARGET_EDGE)
        self._session.execute(delete(KnowledgeEdge).where(KnowledgeEdge.document_id == document_id))
        self._session.execute(delete(KnowledgeNode).where(KnowledgeNode.document_id == document_id))
        self._session.flush()

        root = self._create_node(
            document_id=document_id,
            parent_id=None,
            path="",
            depth=0,
            position=0,
            title=tree.title,
            summary=document_title,
            keywords=[],
            section_indexes=[index for index in sorted(section_chunk_ids)],
            section_chunk_ids=section_chunk_ids,
            max_evidence=MAX_ROOT_EVIDENCE_CHUNKS,
        )
        for position, child in enumerate(tree.children):
            self._create_branch(
                document_id=document_id,
                parent_id=root,
                parent_path="",
                depth=1,
                position=position,
                node=child,
                section_chunk_ids=section_chunk_ids,
            )
        self._session.flush()
        return root

    def _create_branch(
        self,
        *,
        document_id: UUID,
        parent_id: UUID,
        parent_path: str,
        depth: int,
        position: int,
        node: KnowledgeNodeSchema,
        section_chunk_ids: dict[int, list[UUID]],
    ) -> UUID:
        path = f"{parent_path}.{position}" if parent_path else f"{position}"
        node_id = self._create_node(
            document_id=document_id,
            parent_id=parent_id,
            path=path,
            depth=depth,
            position=position,
            title=node.title,
            summary=node.summary,
            keywords=node.keywords,
            section_indexes=node.source_section_indexes,
            section_chunk_ids=section_chunk_ids,
        )
        edge = KnowledgeEdge(
            id=uuid4(),
            document_id=document_id,
            parent_node_id=parent_id,
            child_node_id=node_id,
            relation="contains",
        )
        self._session.add(edge)
        self._session.flush()

        child_evidence = self._evidence.chunk_ids_for_target(EVIDENCE_TARGET_NODE, node_id)
        if child_evidence:
            self._evidence.add_links(
                document_id=document_id,
                target_type=EVIDENCE_TARGET_EDGE,
                target_id=edge.id,
                chunk_ids=child_evidence[:MAX_EVIDENCE_CHUNKS_PER_NODE],
            )

        for child_position, child in enumerate(node.children):
            self._create_branch(
                document_id=document_id,
                parent_id=node_id,
                parent_path=path,
                depth=depth + 1,
                position=child_position,
                node=child,
                section_chunk_ids=section_chunk_ids,
            )
        return node_id

    def _create_node(
        self,
        *,
        document_id: UUID,
        parent_id: UUID | None,
        path: str,
        depth: int,
        position: int,
        title: str,
        summary: str,
        keywords: list[str],
        section_indexes: list[int],
        section_chunk_ids: dict[int, list[UUID]],
        max_evidence: int = MAX_EVIDENCE_CHUNKS_PER_NODE,
    ) -> UUID:
        node_id = uuid4()
        self._session.add(
            KnowledgeNode(
                id=node_id,
                document_id=document_id,
                parent_id=parent_id,
                path=path,
                depth=depth,
                position=position,
                title=title,
                summary=summary,
                keywords=keywords,
            )
        )
        self._session.flush()

        for section_index in section_indexes:
            chunk_ids = section_chunk_ids.get(section_index, [])
            if not chunk_ids:
                continue
            self._evidence.add_links(
                document_id=document_id,
                target_type=EVIDENCE_TARGET_NODE,
                target_id=node_id,
                chunk_ids=chunk_ids[:max_evidence],
                source_section_index=section_index,
            )
        return node_id

    def get_node(self, node_id: UUID) -> KnowledgeNode | None:
        return self._session.get(KnowledgeNode, node_id)

    def get_tree_nodes(self, document_id: UUID) -> list[KnowledgeNode]:
        return (
            self._session.execute(
                select(KnowledgeNode)
                .where(KnowledgeNode.document_id == document_id)
                .order_by(KnowledgeNode.depth, KnowledgeNode.position)
            )
            .scalars()
            .all()
        )

    def ancestors(self, node: KnowledgeNode) -> list[KnowledgeNode]:
        """Root-first ancestors of a node, used to build the Node Context breadcrumb."""
        chain: list[KnowledgeNode] = []
        parent_id = node.parent_id
        while parent_id is not None and len(chain) < 10:
            parent = self._session.get(KnowledgeNode, parent_id)
            if parent is None:
                break
            chain.append(parent)
            parent_id = parent.parent_id
        return list(reversed(chain))

    def children_of(self, node_id: UUID) -> list[KnowledgeNode]:
        return (
            self._session.execute(
                select(KnowledgeNode)
                .where(KnowledgeNode.parent_id == node_id)
                .order_by(KnowledgeNode.position)
            )
            .scalars()
            .all()
        )

    def siblings_of(self, node: KnowledgeNode) -> list[KnowledgeNode]:
        if node.parent_id is None:
            return []
        return [sibling for sibling in self.children_of(node.parent_id) if sibling.id != node.id]

    def root_node(self, document_id: UUID) -> KnowledgeNode | None:
        return self._session.execute(
            select(KnowledgeNode)
            .where(KnowledgeNode.document_id == document_id, KnowledgeNode.parent_id.is_(None))
            .limit(1)
        ).scalar_one_or_none()

    def node_evidence_chunk_ids(self, node_id: UUID) -> frozenset[UUID]:
        return frozenset(self._evidence.chunk_ids_for_target(EVIDENCE_TARGET_NODE, node_id))

    def node_section_indexes(self, document_id: UUID) -> dict[UUID, list[int]]:
        from app.models.evidence import EvidenceLink

        rows = self._session.execute(
            select(EvidenceLink.target_id, EvidenceLink.source_section_index)
            .where(
                EvidenceLink.document_id == document_id,
                EvidenceLink.target_type == EVIDENCE_TARGET_NODE,
                EvidenceLink.source_section_index.is_not(None),
            )
            .distinct()
        ).all()
        mapping: dict[UUID, list[int]] = {}
        for target_id, section_index in rows:
            mapping.setdefault(target_id, []).append(int(section_index))
        for indexes in mapping.values():
            indexes.sort()
        return mapping

    @staticmethod
    def quote_excerpt(text: str) -> str:
        normalized = " ".join(text.split())
        return normalized[:MAX_QUOTE_CHARACTERS]
