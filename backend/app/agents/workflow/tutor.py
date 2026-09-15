"""Tutor Agent — answers about one node from its Node Context (explain/example/deep dive/quiz)."""

from uuid import UUID

from app.agents.node_qa.agent import NodeQuestionAgent
from app.agents.node_qa.context import NodeContext, build_node_context
from app.agents.node_qa.contracts import EvidenceItem
from app.agents.node_qa.factory import create_node_question_agent
from app.agents.node_qa.degraded import build_degraded_answer
from app.agents.node_qa.intents import NodeIntent, intent_from_value
from app.agents.workflow.state import TutorCitation, TutorQuizItem, TutorReply, WorkflowDependencies
from app.core.config import settings
from app.models.document import Document
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge import KnowledgeRepository
from app.retrieval.retriever import Retriever, create_retriever

MODE_LLM = "llm"
MODE_EXTRACTIVE = "extractive_fallback"
MAX_QUIZ_ITEMS_WITHOUT_MODEL = 4
MAX_QUERY_CHARACTERS = 1200

# The intent shapes retrieval as well as the prompt: an example request looks for cases.
INTENT_QUERY_HINTS: dict[NodeIntent, str] = {
    NodeIntent.EXPLAIN: "定义 含义 是什么 为什么重要",
    NodeIntent.EXAMPLE: "案例 例如 示例 比如 典型",
    NodeIntent.DEEP_DIVE: "要点 展开 关联 影响 路径",
    NodeIntent.QUIZ: "定义 事实 数据 要点",
}


class TutorAgent:
    """Teaching stage: builds the context, asks the model, validates the citations."""

    def __init__(
        self,
        *,
        retriever: Retriever | None = None,
        answer_agent: NodeQuestionAgent | None = None,
        answer_agent_factory=create_node_question_agent,
    ) -> None:
        self._retriever = retriever
        self._answer_agent = answer_agent
        self._answer_agent_factory = answer_agent_factory

    def teach(
        self,
        deps: WorkflowDependencies,
        *,
        node_id: UUID,
        intent_value: str,
        question: str = "",
    ) -> TutorReply:
        knowledge = KnowledgeRepository(deps.session)
        node = knowledge.get_node(node_id)
        if node is None:
            raise LookupError(f"Knowledge node {node_id} does not exist.")

        intent = intent_from_value(intent_value)
        children = knowledge.children_of(node.id)
        context = self._build_context(deps, node, children, intent, question)
        if not context.evidence:
            return TutorReply(
                node_id=node.id,
                intent=intent.value,
                mode=MODE_EXTRACTIVE,
                refused=True,
                refusal_reason="No content block in this document matched the request closely enough.",
                context_truncated=context.truncated,
            )

        if settings.chat_model_configured:
            agent = self._answer_agent or self._answer_agent_factory()
            result = agent.answer(context=context, intent=intent, question=question)
            mode = MODE_LLM
        else:
            result = build_degraded_answer(context, intent)
            mode = MODE_EXTRACTIVE

        evidence_by_chunk = {item.chunk_id: item for item in context.evidence}
        citations = [
            _citation(evidence_by_chunk[chunk_id])
            for chunk_id in result.cited_chunk_ids
            if chunk_id in evidence_by_chunk
        ]
        quiz_items = [
            TutorQuizItem(
                question=item.question,
                answer=item.answer,
                citations=[
                    _citation(evidence_by_chunk[chunk_id])
                    for chunk_id in item.cited_chunk_ids
                    if chunk_id in evidence_by_chunk
                ],
            )
            for item in result.quiz_items
        ]
        return TutorReply(
            node_id=node.id,
            intent=intent.value,
            mode=mode,
            answer=result.answer,
            citations=citations,
            quiz_items=quiz_items,
            refused=result.refused,
            refusal_reason=result.refusal_reason,
            confidence=result.confidence,
            context_truncated=context.truncated,
        )

    def _build_context(
        self,
        deps: WorkflowDependencies,
        node,
        children,
        intent: NodeIntent,
        question: str,
    ) -> NodeContext:
        knowledge = KnowledgeRepository(deps.session)
        retriever = self._retriever or deps.retriever or create_retriever(deps.session)
        results = retriever.retrieve(
            document_id=node.document_id,
            query=_build_query(node, question, intent, children),
            node_evidence_chunk_ids=knowledge.node_evidence_chunk_ids(node.id),
        )
        evidence = [
            EvidenceItem(
                label=f"c{index}",
                chunk_id=result.chunk_id,
                text=result.text,
                location=result.location_label,
                section_title=result.section_title,
                score=result.score,
            )
            for index, result in enumerate(results, start=1)
        ]
        root = knowledge.root_node(node.document_id)
        document: Document | None = DocumentRepository(deps.session).get(node.document_id)
        return build_node_context(
            document_title=root.title if root is not None else (document.original_filename if document else ""),
            node_title=node.title,
            node_summary=node.summary,
            keywords=list(node.keywords or []),
            breadcrumb=[ancestor.title for ancestor in knowledge.ancestors(node)],
            children=[(child.title, child.summary) for child in children],
            siblings=[sibling.title for sibling in knowledge.siblings_of(node)],
            evidence=evidence,
        )


def _build_query(node, question_text: str, intent: NodeIntent, children) -> str:
    parts = [node.title, node.summary, INTENT_QUERY_HINTS.get(intent, ""), question_text]
    if intent == NodeIntent.DEEP_DIVE:
        parts.extend(child.title for child in children[:6])
    return "\n".join(part for part in parts if part).strip()[:MAX_QUERY_CHARACTERS]


def _citation(evidence: EvidenceItem) -> TutorCitation:
    return TutorCitation(
        chunk_id=evidence.chunk_id,
        quote=" ".join(evidence.text.split())[:240],
        section_title=evidence.section_title,
        location=evidence.location,
        relevance=evidence.score,
    )
