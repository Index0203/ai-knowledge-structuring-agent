"""Degraded-mode answers used when no chat model is configured."""

from app.agents.node_qa.context import NodeContext
from app.agents.node_qa.contracts import NodeAnswerResult, NodeQuizItem
from app.agents.node_qa.fallback import build_extractive_answer
from app.agents.node_qa.intents import NodeIntent

MAX_QUIZ_ITEMS_WITHOUT_MODEL = 4


def build_degraded_answer(context: NodeContext, intent: NodeIntent) -> NodeAnswerResult:
    """Quotes for normal requests, outline-derived questions for quizzes."""
    if intent == NodeIntent.QUIZ:
        return _outline_quiz(context)
    return build_extractive_answer(list(context.evidence))


def _outline_quiz(context: NodeContext) -> NodeAnswerResult:
    """Questions derived from the node's own outline, each backed by its evidence."""
    fallback_chunk = context.evidence[0].chunk_id
    items: list[NodeQuizItem] = []
    for title, summary in context.children[:MAX_QUIZ_ITEMS_WITHOUT_MODEL]:
        items.append(
            NodeQuizItem(
                question=f"请说明「{title}」的含义及其作用。",
                answer=summary,
                cited_chunk_ids=(fallback_chunk,),
            )
        )
    if not items:
        items.append(
            NodeQuizItem(
                question=f"请用自己的话解释「{context.node_title}」。",
                answer=context.node_summary or context.node_title,
                cited_chunk_ids=(fallback_chunk,),
            )
        )
    return NodeAnswerResult(
        answer=f"未配置模型，以下测试题依据该节点的子节点生成，共 {len(items)} 题。",
        cited_chunk_ids=(fallback_chunk,),
        confidence=0.3,
        quiz_items=tuple(items),
    )
