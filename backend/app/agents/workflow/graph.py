"""The LangGraph multi-agent workflow.

    START → Planner → execute_step ─┬─(more steps)→ execute_step
                                    └─(done/failed)→ END

The Planner turns a request into an ordered plan; `execute_step` runs the agent of
the current step and appends a trace. Agents only write their own artifact, so every
step is independently testable and the journal explains what ran.
"""

import time
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.workflow.document_analyst import DocumentAnalystAgent
from app.agents.workflow.knowledge_extraction import KnowledgeExtractionAgent
from app.agents.workflow.planner import PlannerAgent, create_planner_agent
from app.agents.workflow.state import (
    AgentName,
    AgentTrace,
    TaskType,
    WorkflowDependencies,
    WorkflowRequest,
    WorkflowState,
    WorkflowStatus,
)
from app.agents.workflow.tutor import TutorAgent
from app.agents.workflow.visualization import VisualizationAgent
from app.core.config import settings

EXECUTE_STEP = "execute_step"


def planner_node(state: WorkflowState) -> dict[str, Any]:
    request = state["request"]
    planner = PlannerAgent() if state.get("deps") is None else _planner_for(state["deps"])
    plan = planner.plan(request)
    trace = AgentTrace(
        agent=AgentName.PLANNER,
        status="ok",
        detail=f"{plan.task_type} · {plan.reason}（{plan.analysed_by}）",
        used_model=plan.analysed_by.startswith("model"),
    )
    return {"plan": plan, "current_step": 0, "status": WorkflowStatus.RUNNING, "traces": [trace]}


def execute_step(state: WorkflowState) -> dict[str, Any]:
    """Run the agent of the current step and journal the outcome."""
    plan = state["plan"]
    index = state.get("current_step", 0)
    if index >= len(plan.steps):
        return {}
    step = plan.steps[index]
    deps = state["deps"]
    request = state["request"]
    started_at = time.perf_counter()

    try:
        updates = _run_agent(step.agent, state, deps, request)
    except Exception as error:  # noqa: BLE001 - one failed agent stops the workflow cleanly
        trace = AgentTrace(
            agent=step.agent,
            status="failed",
            detail=str(error)[:300],
            duration_ms=int((time.perf_counter() - started_at) * 1000),
        )
        return {
            "current_step": index + 1,
            "status": WorkflowStatus.FAILED,
            "errors": [f"{step.agent}: {error}"],
            "traces": [trace],
        }

    degraded = updates.pop("_degraded", False)
    trace = AgentTrace(
        agent=step.agent,
        status="degraded" if degraded else "ok",
        detail=updates.pop("_detail", step.goal),
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        used_model=settings.chat_model_configured
        and step.agent
        in {AgentName.KNOWLEDGE_EXTRACTION, AgentName.TUTOR, AgentName.PLANNER},
    )
    updates["current_step"] = index + 1
    updates["traces"] = [trace]
    return updates


def _run_agent(
    agent: AgentName,
    state: WorkflowState,
    deps: WorkflowDependencies,
    request: WorkflowRequest,
) -> dict[str, Any]:
    if agent == AgentName.DOCUMENT_ANALYST:
        digest, processed, sections = _analyst(deps).analyse(deps, _require(request.document_id))
        return {
            "digest": digest,
            "sections": sections,
            "processed": processed,
            "_detail": (
                f"{digest.section_count} 节 · {digest.chunk_count} 块 · 结构来源 {digest.structure_source}"
            ),
        }

    if agent == AgentName.KNOWLEDGE_EXTRACTION:
        processed = state.get("processed")
        if processed is None:
            raise ValueError("Knowledge extraction needs the document analyst to run first.")
        tree, knowledge, root_id = _extraction(deps).extract(deps, _require(request.document_id), processed)
        degraded = settings.chat_model_configured and knowledge.mode == "structure_fallback"
        return {
            "tree": tree,
            "knowledge": knowledge,
            "root_node_id": root_id,
            "_degraded": degraded,
            "_detail": f"{knowledge.node_count} 个节点 · 模式 {knowledge.mode}",
        }

    if agent == AgentName.VISUALIZATION:
        model = _visualization().build(deps, _require(request.document_id))
        return {
            "map_model": model,
            "_detail": (
                f"{model.node_count} 个节点 · 最大深度 {model.max_depth} · "
                f"无证据节点 {model.nodes_without_evidence}"
            ),
        }

    if agent == AgentName.TUTOR:
        reply = _tutor(deps).teach(
            deps,
            node_id=_require(request.node_id),
            intent_value=request.node_intent,
            question=request.question,
        )
        return {
            "tutor": reply,
            "_degraded": settings.chat_model_configured and reply.mode == "extractive_fallback",
            "_detail": f"intent={reply.intent} · 引用 {len(reply.citations)} 条 · 测试题 {len(reply.quiz_items)}",
        }

    raise ValueError(f"Agent {agent} has no runner.")


def route_after_step(state: WorkflowState) -> str:
    if state.get("status") == WorkflowStatus.FAILED:
        return "done"
    return "continue" if state.get("current_step", 0) < len(state["plan"].steps) else "done"


def build_agent_workflow():
    """Compile the graph. One instance can serve many runs (it holds no state)."""
    graph = StateGraph(WorkflowState)
    graph.add_node(AgentName.PLANNER, planner_node)
    graph.add_node(EXECUTE_STEP, execute_step)
    graph.add_edge(START, AgentName.PLANNER)
    graph.add_edge(AgentName.PLANNER, EXECUTE_STEP)
    graph.add_conditional_edges(
        EXECUTE_STEP,
        route_after_step,
        {"continue": EXECUTE_STEP, "done": END},
    )
    return graph.compile()


def run_workflow(*, deps: WorkflowDependencies, request: WorkflowRequest) -> WorkflowState:
    """Execute the workflow once and return the final state (artifacts + journal)."""
    workflow = build_agent_workflow()
    state: WorkflowState = {
        "request": request,
        "deps": deps,
        "current_step": 0,
        "status": WorkflowStatus.PENDING,
        "traces": [],
        "errors": [],
    }
    result = workflow.invoke(state)
    if result.get("status") == WorkflowStatus.RUNNING:
        result["status"] = _final_status(result)
    return result


def _final_status(state: WorkflowState) -> str:
    if any(trace.status == "degraded" for trace in state.get("traces", [])):
        return WorkflowStatus.DEGRADED
    return WorkflowStatus.SUCCEEDED


# --------------------------------------------------------------- collaborators


def _planner_for(deps: WorkflowDependencies) -> PlannerAgent:
    factory = deps.metadata.get("planner_factory")
    return factory() if factory else create_planner_agent()


def _analyst(deps: WorkflowDependencies) -> DocumentAnalystAgent:
    return DocumentAnalystAgent(deps.processing_service)


def _extraction(deps: WorkflowDependencies) -> KnowledgeExtractionAgent:
    if deps.enrichment_agent_factory is not None:
        return KnowledgeExtractionAgent(deps.enrichment_agent_factory)
    return KnowledgeExtractionAgent()


def _visualization() -> VisualizationAgent:
    return VisualizationAgent()


def _tutor(deps: WorkflowDependencies) -> TutorAgent:
    kwargs: dict[str, Any] = {
        "retriever": deps.retriever,
        "answer_agent": deps.metadata.get("answer_agent"),
    }
    if deps.answer_agent_factory is not None:
        kwargs["answer_agent_factory"] = deps.answer_agent_factory
    return TutorAgent(**kwargs)


def _require(value):
    if value is None:
        raise ValueError("The plan needs an identifier that this request did not provide.")
    return value


def task_type_of(state: WorkflowState) -> TaskType:
    return state["plan"].task_type
