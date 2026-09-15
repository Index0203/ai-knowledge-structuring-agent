"""Visualization Agent — turns the stored knowledge structure into a renderable map model."""

from uuid import UUID

from app.agents.workflow.state import MapEdge, MapModel, MapNode, WorkflowDependencies
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge import KnowledgeRepository

SCHEMA_VERSION = "knowledge-map-v1"


class VisualizationAgent:
    """Produces the view model the frontend renders (structure only, no layout pixels)."""

    def build(self, deps: WorkflowDependencies, document_id: UUID) -> MapModel:
        knowledge = KnowledgeRepository(deps.session)
        rows = knowledge.get_tree_nodes(document_id)
        if not rows:
            raise ValueError(f"Document {document_id} has no knowledge nodes to visualise.")

        section_indexes = knowledge.node_section_indexes(document_id)
        children_by_parent: dict[UUID | None, list] = {}
        for row in rows:
            children_by_parent.setdefault(row.parent_id, []).append(row)

        edges: list[MapEdge] = []
        nodes_without_evidence = 0

        def build(row, path: str) -> MapNode:
            nonlocal nodes_without_evidence
            children = []
            # Edges are recorded parent-first so the map model reads top-down.
            for index, child_row in enumerate(children_by_parent.get(row.id, [])):
                child_path = f"{path}.{index}" if path else str(index)
                edges.append(MapEdge(source=path, target=child_path))
                children.append(build(child_row, child_path))
            evidence_sections = section_indexes.get(row.id, [])
            if not evidence_sections:
                nodes_without_evidence += 1
            return MapNode(
                id=row.id,
                path=path,
                title=row.title,
                depth=row.depth,
                child_count=len(children),
                keyword_count=len(row.keywords or []),
                evidence_sections=evidence_sections,
                children=children,
            )

        root_row = next((row for row in rows if row.parent_id is None), None)
        if root_row is None:
            raise ValueError(f"Document {document_id} has no root node.")
        root = build(root_row, "")

        document = DocumentRepository(deps.session).get(document_id)
        model = MapModel(
            schema_version=SCHEMA_VERSION,
            document_id=document_id,
            title=root.title,
            root=root,
            edges=edges,
            node_count=sum(1 for _row in rows),
            max_depth=max((row.depth for row in rows), default=0),
            chapter_count=len(children_by_parent.get(root.id, [])),
            nodes_without_evidence=nodes_without_evidence,
        )
        _persist(deps, document, model)
        return model


def _persist(deps: WorkflowDependencies, document, model: MapModel) -> None:
    """Store the map model next to the document so the API can serve it without rebuilding."""
    if document is None:
        return
    document.map_model = model.model_dump(mode="json")
    deps.session.flush()
