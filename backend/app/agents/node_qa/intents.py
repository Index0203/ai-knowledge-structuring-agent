"""The four assistant capabilities a knowledge node offers."""

from enum import StrEnum


class NodeIntent(StrEnum):
    """What the user asked the node assistant to do."""

    EXPLAIN = "explain"
    EXAMPLE = "example"
    DEEP_DIVE = "deep_dive"
    QUIZ = "quiz"
    ASK = "ask"


INTENT_INSTRUCTIONS: dict[NodeIntent, str] = {
    NodeIntent.EXPLAIN: (
        "Explain this node to someone who has never read the document: what it is, why it matters, "
        "and how it relates to its parent and sibling nodes. Start from the node's definition when the "
        "context contains one. Keep it to a few short paragraphs."
    ),
    NodeIntent.EXAMPLE: (
        "Illustrate this node with examples. Prefer examples, cases or numbers that appear in the context "
        "(look for 案例 / 例如 / 比如 / 示例). If the context contains none, say so explicitly and mark any "
        "illustration you add as 示意（非文档内容）."
    ),
    NodeIntent.DEEP_DIVE: (
        "Help the reader study this node in depth: break it into its sub-points, explain how they relate, "
        "and end with what to read next inside this document (child nodes or nearby sections)."
    ),
    NodeIntent.QUIZ: (
        "Write 3-5 test questions that check understanding of this node, from factual recall to application. "
        "Each question must be answerable from the context alone. Put every question with its reference "
        "answer into quiz_items, and keep the main answer to a one-sentence introduction."
    ),
    NodeIntent.ASK: "Answer the user's question using only the context.",
}


def intent_from_value(value: str) -> NodeIntent:
    try:
        return NodeIntent(value)
    except ValueError:
        return NodeIntent.ASK
