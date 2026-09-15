from typing import TypedDict
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.node_qa.context import NodeContext
from app.agents.node_qa.contracts import (
    AnswerDraftModel,
    EvidenceItem,
    NodeAnswerResult,
    NodeQuizItem,
)
from app.agents.node_qa.intents import NodeIntent
from app.agents.node_qa.prompts import SYSTEM_PROMPT, build_node_assistant_prompt
from app.schemas.answers import AnswerDraft

REFUSAL_NO_EVIDENCE = "This node has no evidence block in the document, so the assistant cannot answer."


class NodeAssistantState(TypedDict):
    context: NodeContext
    intent: NodeIntent
    question: str
    draft: AnswerDraft
    result: NodeAnswerResult


class NodeQuestionAgent:
    """Bounded LangGraph workflow: draft an answer from the Node Context, then verify citations."""

    def __init__(self, model: AnswerDraftModel) -> None:
        self._model = model
        self._graph = self._build_graph()

    def answer(
        self,
        *,
        context: NodeContext,
        intent: NodeIntent = NodeIntent.ASK,
        question: str = "",
    ) -> NodeAnswerResult:
        if context.is_empty() or not context.evidence:
            return NodeAnswerResult(
                answer=None,
                refused=True,
                refusal_reason=REFUSAL_NO_EVIDENCE,
            )
        state = self._graph.invoke({"context": context, "intent": intent, "question": question})
        return state["result"]

    def _build_graph(self):
        graph = StateGraph(NodeAssistantState)
        graph.add_node("draft_answer", self._draft_answer)
        graph.add_node("validate_citations", self._validate_citations)
        graph.add_edge(START, "draft_answer")
        graph.add_edge("draft_answer", "validate_citations")
        graph.add_edge("validate_citations", END)
        return graph.compile()

    def _draft_answer(self, state: NodeAssistantState) -> dict[str, AnswerDraft]:
        prompt = build_node_assistant_prompt(
            context=state["context"],
            intent=state["intent"],
            question=state["question"],
        )
        response = self._model.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(prompt)])
        return {"draft": AnswerDraft.model_validate(response)}

    @staticmethod
    def _validate_citations(state: NodeAssistantState) -> dict[str, NodeAnswerResult]:
        draft = state["draft"]
        evidence_by_label = {item.label: item for item in state["context"].evidence}

        if draft.insufficient_evidence:
            return {
                "result": NodeAnswerResult(
                    answer=None,
                    confidence=draft.confidence,
                    refused=True,
                    refusal_reason="The node context does not contain the information needed for this request.",
                )
            }

        cited = _resolve(draft.cited_evidence_ids, evidence_by_label)
        quiz_items = tuple(
            NodeQuizItem(
                question=item.question.strip(),
                answer=item.answer.strip(),
                cited_chunk_ids=tuple(_resolve(item.cited_evidence_ids, evidence_by_label)),
            )
            for item in draft.quiz_items
        )
        if state["intent"] == NodeIntent.QUIZ:
            quiz_items = tuple(item for item in quiz_items if item.cited_chunk_ids)
        else:
            # Only the quiz capability returns test questions, whatever the model volunteered.
            quiz_items = ()

        if not cited and not quiz_items:
            # An answer without a verifiable citation must not reach the user.
            return {
                "result": NodeAnswerResult(
                    answer=None,
                    confidence=draft.confidence,
                    refused=True,
                    refusal_reason="The answer could not be traced to any retrieved content block.",
                )
            }

        return {
            "result": NodeAnswerResult(
                answer=draft.answer.strip(),
                cited_chunk_ids=tuple(cited),
                confidence=draft.confidence,
                refused=False,
                quiz_items=quiz_items,
            )
        }


def _resolve(labels: list[str], evidence_by_label: dict[str, EvidenceItem]) -> list[UUID]:
    resolved: list[UUID] = []
    for label in labels:
        item = evidence_by_label.get(label.strip().lower())
        if item is not None and item.chunk_id not in resolved:
            resolved.append(item.chunk_id)
    return resolved
