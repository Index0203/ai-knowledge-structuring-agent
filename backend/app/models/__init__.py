"""SQLAlchemy persistence models.

Importing this package registers every table on `Base.metadata`, which Alembic
and the test fixtures rely on.
"""

from app.models.chunk import ContentChunk
from app.models.document import Document
from app.models.evidence import EvidenceLink
from app.models.knowledge import KnowledgeEdge, KnowledgeNode
from app.models.question import Question

__all__ = ["ContentChunk", "Document", "EvidenceLink", "KnowledgeEdge", "KnowledgeNode", "Question"]
