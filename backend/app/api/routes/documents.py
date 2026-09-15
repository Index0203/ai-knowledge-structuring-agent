from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.knowledge_tree_api import KnowledgeTreeResponse
from app.schemas.pipeline import DocumentStatusResponse, ProcessingAcceptedResponse
from app.services import document_service
from app.services.knowledge_tree_service import KnowledgeTreeNotFoundError, load_tree_response
from app.workers.dispatch import (
    TaskDispatchError,
    dispatch_build_knowledge_tree,
    dispatch_index_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}", response_model=DocumentStatusResponse)
def read_document(document_id: UUID, session: Session = Depends(get_session)) -> DocumentStatusResponse:
    """Return processing and knowledge-tree status for one document."""
    try:
        return document_service.get_document_status(session, document_id)
    except document_service.DocumentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/{document_id}/processing", response_model=ProcessingAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def start_processing(document_id: UUID, session: Session = Depends(get_session)) -> ProcessingAcceptedResponse:
    """Queue chunking, embedding and vector indexing for one document."""
    try:
        return document_service.request_indexing(session, document_id, dispatch_index_document)
    except document_service.DocumentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except TaskDispatchError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.post(
    "/{document_id}/knowledge-tree",
    response_model=ProcessingAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_knowledge_tree(document_id: UUID, session: Session = Depends(get_session)) -> ProcessingAcceptedResponse:
    """Queue knowledge extraction for a document that has been indexed."""
    try:
        return document_service.request_tree_build(session, document_id, dispatch_build_knowledge_tree)
    except document_service.DocumentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except TaskDispatchError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


@router.get("/{document_id}/knowledge-tree", response_model=KnowledgeTreeResponse)
def read_knowledge_tree(document_id: UUID, session: Session = Depends(get_session)) -> KnowledgeTreeResponse:
    """Return the persisted knowledge tree, or the current build status."""
    try:
        return load_tree_response(session, document_id)
    except KnowledgeTreeNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
