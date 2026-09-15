from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas.uploads import UploadResponse
from app.services.upload_service import UploadError, upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), session: Session = Depends(get_session)) -> UploadResponse:
    """Persist a supported document after validating its extension and file signature."""
    try:
        return await upload_service.save_upload(file, session)
    except UploadError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
