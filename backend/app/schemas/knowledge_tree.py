from pydantic import BaseModel, ConfigDict, Field


class KnowledgeNode(BaseModel):
    """A schema-validated, user-facing node in an extracted knowledge tree."""

    # Model output: required fields are validated, unknown fields are ignored.
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=600)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    source_section_indexes: list[int] = Field(min_length=1, max_length=24)
    children: list["KnowledgeNode"] = Field(default_factory=list, max_length=64)


class KnowledgeTree(BaseModel):
    """Stable JSON contract returned by the knowledge extraction workflow."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=160)
    children: list[KnowledgeNode] = Field(default_factory=list, max_length=64)
