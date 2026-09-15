"""State and payload contracts for the multi-agent workflow.

Every agent reads the shared state and writes back only its own artifact plus a
trace entry, so the graph stays inspectable and each step can be replayed.
"""

import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.retrieval.retriever import Retriever
from app.schemas.documents import DocumentSection, ProcessedDocument
from app.schemas.knowledge_tree import KnowledgeTree


class AgentName(StrEnum):
    PLANNER = "planner"
    DOCUMENT_ANALYST = "document_analyst"
    KNOWLEDGE_EXTRACTION = "knowledge_extraction"
    VISUALIZATION = "visualization"
    TUTOR = "tutor"


class TaskType(StrEnum):
    BUILD_KNOWLEDGE_MAP = "build_knowledge_map"
    ANALYZE_DOCUMENT = "analyze_document"
    TEACH_NODE = "teach_node"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEGRADED = "degraded"
    FAILED = "failed"


class PlanStep(BaseModel):
    """One unit of delegated work."""

    agent: AgentName
    goal: str = Field(min_length=1, max_length=200)


class WorkflowPlan(BaseModel):
    """Output of the Planner Agent and the routing table for the graph."""

    task_type: TaskType
    steps: list[PlanStep] = Field(default_factory=list)
    reason: str = Field(default="", max_length=400)
    analysed_by: str = Field(default="rules", max_length=32)


class DocumentDigest(BaseModel):
    """What the Document Analyst learned about the source document."""

    document_id: UUID
    title: str
    structure_source: str | None = None
    parser_name: str = ""
    page_count: int | None = None
    paragraph_count: int | None = None
    ocr_page_count: int | None = None
    section_count: int = 0
    chunk_count: int = 0
    outline: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class KnowledgeDraft(BaseModel):
    """Output of the Knowledge Extraction Agent."""

    mode: str
    node_count: int
    max_depth: int
    labels: list[str] = Field(default_factory=list)


class MapEdge(BaseModel):
    source: str
    target: str
    relation: str = "contains"


class MapNode(BaseModel):
    """One renderable node of the knowledge map."""

    id: UUID
    path: str
    title: str
    depth: int
    child_count: int
    keyword_count: int
    evidence_sections: list[int] = Field(default_factory=list)
    children: list["MapNode"] = Field(default_factory=list)


class MapModel(BaseModel):
    """Output of the Visualization Agent: the structure the UI renders."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "knowledge-map-v1"
    document_id: UUID
    title: str
    root: MapNode
    edges: list[MapEdge] = Field(default_factory=list)
    node_count: int = 0
    max_depth: int = 0
    chapter_count: int = 0
    nodes_without_evidence: int = 0


class TutorCitation(BaseModel):
    chunk_id: UUID
    quote: str
    section_title: str
    location: str
    relevance: float


class TutorQuizItem(BaseModel):
    question: str
    answer: str
    citations: list[TutorCitation] = Field(default_factory=list)


class TutorReply(BaseModel):
    """Output of the Tutor Agent, before persistence."""

    node_id: UUID
    intent: str
    mode: str
    answer: str | None = None
    citations: list[TutorCitation] = Field(default_factory=list)
    quiz_items: list[TutorQuizItem] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    confidence: float | None = None
    context_truncated: bool = False


class AgentTrace(BaseModel):
    """One line of the workflow journal: who ran, whether it worked, how long."""

    agent: AgentName
    status: str
    detail: str = ""
    duration_ms: int = 0
    used_model: bool = False


@dataclass(frozen=True)
class WorkflowRequest:
    """What the caller wants, before the Planner decides how to get there."""

    task_type: TaskType | None = None
    document_id: UUID | None = None
    node_id: UUID | None = None
    node_intent: str = "ask"
    question: str = ""
    instruction: str = ""


@dataclass
class WorkflowDependencies:
    """Runtime collaborators (never serialised, the workflow runs in-process)."""

    session: Session
    upload_dir: str
    processing_service: Any = None
    chunking_service: Any = None
    enrichment_agent_factory: Callable[[], Any] | None = None
    retriever: Retriever | None = None
    answer_agent_factory: Callable[[], Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowState(TypedDict, total=False):
    """The graph state.

    Artifacts are additive: each agent fills in its own key and leaves the rest
    untouched. `traces`/`errors` use the add reducer so parallel or retried steps
    append instead of overwriting each other.
    """

    request: WorkflowRequest
    deps: WorkflowDependencies
    plan: WorkflowPlan
    current_step: int
    status: str
    # artifacts
    digest: DocumentDigest
    sections: list[DocumentSection]
    processed: ProcessedDocument
    tree: KnowledgeTree
    root_node_id: UUID
    knowledge: KnowledgeDraft
    map_model: MapModel
    tutor: TutorReply
    # journal
    traces: Annotated[list[AgentTrace], operator.add]
    errors: Annotated[list[str], operator.add]
