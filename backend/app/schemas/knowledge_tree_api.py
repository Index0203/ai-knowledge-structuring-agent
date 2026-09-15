from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeTreeNodeResponse(BaseModel):
    id: UUID
    title: str
    summary: str
    keywords: list[str] = Field(default_factory=list)
    source_section_indexes: list[int] = Field(default_factory=list)
    depth: int
    children: list["KnowledgeTreeNodeResponse"] = Field(default_factory=list)


class KnowledgeTreeResponse(BaseModel):
    document_id: UUID
    status: str
    mode: str | None
    error_message: str | None
    tree: KnowledgeTreeNodeResponse | None
    map: dict[str, object] | None = None
