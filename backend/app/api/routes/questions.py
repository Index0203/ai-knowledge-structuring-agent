from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.answers import QuestionAnswerResponse, QuestionSubmittedResponse
from app.services.question_service import QuestionNotFoundError, QuestionService, load_question_answer
from app.workers.dispatch import TaskDispatchError
from app.agents.node_qa.intents import NodeIntent, intent_from_value

router = APIRouter(tags=["questions"])


class QuestionRequest(BaseModel):
    """A free-form question, an assistant intent, or both."""

    question: str = Field(default="", max_length=1000)
    intent: str = Field(default="ask", max_length=32)


DEFAULT_INTENT_QUESTIONS: dict[NodeIntent, str] = {
    NodeIntent.EXPLAIN: "请解释这个节点。",
    NodeIntent.EXAMPLE: "请举例说明这个节点。",
    NodeIntent.DEEP_DIVE: "我想深入学习这个节点。",
    NodeIntent.QUIZ: "请根据这个节点生成测试问题。",
    NodeIntent.ASK: "",
}


@router.post(
    "/knowledge-nodes/{node_id}/questions",
    response_model=QuestionSubmittedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_question(
    node_id: UUID,
    payload: QuestionRequest,
    session: Session = Depends(get_session),
) -> QuestionSubmittedResponse:
    """Queue a grounded question about one knowledge node."""
    service = QuestionService(session)
    intent = intent_from_value(payload.intent)
    question_text = payload.question.strip() or DEFAULT_INTENT_QUESTIONS[intent]
    if len(question_text) < 2:
        raise HTTPException(
            status_code=422,
            detail="A question needs at least two characters.",
        )
    try:
        question = service.submit(node_id=node_id, question_text=question_text, intent=intent.value)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except TaskDispatchError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return QuestionSubmittedResponse(
        question_id=question.id,
        node_id=question.node_id,
        intent=question.intent,
        status=question.status,
        created_at=question.created_at,
    )


@router.get("/questions/{question_id}", response_model=QuestionAnswerResponse)
def read_question(question_id: UUID, session: Session = Depends(get_session)) -> QuestionAnswerResponse:
    """Return the answer, refusal reason and citations for one question."""
    try:
        return load_question_answer(session, question_id)
    except QuestionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
