from typing import Protocol

from langchain_core.messages import BaseMessage

from app.schemas.knowledge_tree import KnowledgeTree


class StructuredKnowledgeTreeModel(Protocol):
    """A model that returns data conforming to the KnowledgeTree schema."""

    def invoke(self, messages: list[BaseMessage]) -> KnowledgeTree | dict[str, object]:
        """Generate a structured knowledge tree from the provided messages."""
