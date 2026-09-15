from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.repositories.documents import DocumentRepository
from app.schemas.uploads import UploadResponse

PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
SUPPORTED_EXTENSIONS = {".pdf": PDF_MEDIA_TYPE, ".docx": DOCX_MEDIA_TYPE}
CHUNK_SIZE_BYTES = 1024 * 1024


class UploadError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UploadService:
    async def save_upload(self, uploaded_file: UploadFile, session: Session) -> UploadResponse:
        original_filename = self._get_safe_filename(uploaded_file.filename)
        expected_media_type = SUPPORTED_EXTENSIONS.get(Path(original_filename).suffix.lower())
        if expected_media_type is None:
            raise UploadError("Only PDF and DOCX files are supported.", 415)

        document_id = uuid4()
        storage_key = f"{document_id}{Path(original_filename).suffix.lower()}"
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / storage_key
        try:
            size_bytes = await self._write_with_size_limit(uploaded_file, destination)
            self._validate_file_content(destination, expected_media_type)
        except UploadError:
            destination.unlink(missing_ok=True)
            raise
        except OSError as error:
            destination.unlink(missing_ok=True)
            raise UploadError("The uploaded file could not be saved.", 500) from error
        finally:
            await uploaded_file.close()

        try:
            DocumentRepository(session).add(
                Document(
                    id=document_id,
                    original_filename=original_filename,
                    media_type=expected_media_type,
                    storage_key=storage_key,
                    size_bytes=size_bytes,
                )
            )
            session.commit()
        except Exception as error:  # noqa: BLE001 - storage and database must stay consistent
            session.rollback()
            destination.unlink(missing_ok=True)
            raise UploadError("The uploaded file could not be registered.", 500) from error

        return UploadResponse(
            document_id=document_id,
            original_filename=original_filename,
            media_type=expected_media_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            uploaded_at=datetime.now(UTC),
        )

    @staticmethod
    def _get_safe_filename(filename: str | None) -> str:
        if not filename:
            raise UploadError("A filename is required.", 422)
        safe_filename = Path(filename.replace("\\", "/")).name
        if safe_filename in {"", ".", ".."}:
            raise UploadError("The filename is invalid.", 422)
        return safe_filename

    @staticmethod
    async def _write_with_size_limit(uploaded_file: UploadFile, destination: Path) -> int:
        total_size = 0
        with destination.open("wb") as output_file:
            while chunk := await uploaded_file.read(CHUNK_SIZE_BYTES):
                total_size += len(chunk)
                if total_size > settings.max_upload_size_bytes:
                    raise UploadError(
                        f"File size exceeds the {settings.max_upload_size_bytes // (1024 * 1024)} MB limit.",
                        413,
                    )
                output_file.write(chunk)
        if total_size == 0:
            raise UploadError("The uploaded file is empty.", 422)
        return total_size

    @staticmethod
    def _validate_file_content(file_path: Path, expected_media_type: str) -> None:
        if expected_media_type == PDF_MEDIA_TYPE:
            with file_path.open("rb") as file_handle:
                if file_handle.read(5) != b"%PDF-":
                    raise UploadError("The file content is not a valid PDF.", 422)
            return
        try:
            with ZipFile(file_path) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise UploadError("The file content is not a valid DOCX document.", 422)
        except BadZipFile as error:
            raise UploadError("The file content is not a valid DOCX document.", 422) from error


upload_service = UploadService()
