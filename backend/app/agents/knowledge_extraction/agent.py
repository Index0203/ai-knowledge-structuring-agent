from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.knowledge_extraction.contracts import StructuredKnowledgeTreeModel
from app.agents.knowledge_extraction.prompts import SYSTEM_PROMPT, build_knowledge_extraction_prompt
from app.schemas.documents import ProcessedDocument
from app.schemas.knowledge_tree import KnowledgeTree


class KnowledgeExtractionState(TypedDict):
    document: ProcessedDocument
    knowledge_tree: KnowledgeTree


class KnowledgeExtractionAgent:
    """A bounded LangGraph workflow for schema-constrained knowledge extraction."""

    def __init__(self, model: StructuredKnowledgeTreeModel) -> None:
        self._model = model
        self._graph = self._build_graph()

    def extract(self, document: ProcessedDocument) -> KnowledgeTree:
        state = self._graph.invoke({"document": document})
        return state["knowledge_tree"]

    def _build_graph(self):
        graph = StateGraph(KnowledgeExtractionState)
        graph.add_node("extract_knowledge_tree", self._extract_knowledge_tree)
        graph.add_edge(START, "extract_knowledge_tree")
        graph.add_edge("extract_knowledge_tree", END)
        return graph.compile()

    def _extract_knowledge_tree(self, state: KnowledgeExtractionState) -> dict[str, KnowledgeTree]:
        prompt = build_knowledge_extraction_prompt(state["document"])
        response = self._model.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(prompt)])
        return {"knowledge_tree": KnowledgeTree.model_validate(response)}
