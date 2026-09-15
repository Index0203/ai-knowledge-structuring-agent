from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    document_id: UUID
    original_filename: str = Field(min_length=1)
    media_type: str
    size_bytes: int = Field(ge=1)
    storage_key: str
    uploaded_at: datetime
