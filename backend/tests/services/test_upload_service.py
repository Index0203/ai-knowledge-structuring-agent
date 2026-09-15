"""Upload service: filename safety, size boundaries and container validation."""

import asyncio
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.services.upload_service import UploadError, upload_service

PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_upload(payload: bytes, filename: str, content_type: str) -> UploadFile:
    return UploadFile(file=BytesIO(payload), filename=filename, headers={"content-type": content_type})


def make_docx(document_xml: bool = True) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        if document_xml:
            archive.writestr("word/document.xml", "<w:document />")
        else:
            archive.writestr("word/other.xml", "<x />")
    return buffer.getvalue()


def test_windows_style_path_in_filename_is_stripped(session_factory, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    with session_factory() as session:
        response = asyncio.run(
            upload_service.save_upload(make_upload(b"%PDF-1.7", r"..\..\evil.pdf", PDF_MEDIA_TYPE), session)
        )

    assert response.original_filename == "evil.pdf"
    assert (tmp_path / response.storage_key).exists()
    assert not (tmp_path.parent / "evil.pdf").exists()


def test_upload_without_a_filename_is_rejected(session_factory, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    with session_factory() as session:
        with pytest.raises(UploadError) as error:
            asyncio.run(
                upload_service.save_upload(make_upload(b"%PDF-1.7", "", PDF_MEDIA_TYPE), session)
            )

    assert error.value.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_size_limit_is_inclusive(session_factory, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_size_bytes", 10)
    with session_factory() as session:
        accepted = asyncio.run(
            upload_service.save_upload(make_upload(b"%PDF-12345", "exact.pdf", PDF_MEDIA_TYPE), session)
        )
        with pytest.raises(UploadError) as error:
            asyncio.run(
                upload_service.save_upload(make_upload(b"%PDF-123456", "over.pdf", PDF_MEDIA_TYPE), session)
            )

    assert accepted.size_bytes == 10
    assert error.value.status_code == 413
    # The rejected upload must not leave a file behind.
    assert len(list(tmp_path.iterdir())) == 1


def test_docx_without_the_document_part_is_rejected(session_factory, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    with session_factory() as session:
        with pytest.raises(UploadError) as error:
            asyncio.run(
                upload_service.save_upload(make_upload(make_docx(False), "broken.docx", DOCX_MEDIA_TYPE), session)
            )

    assert error.value.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_file_that_lies_about_its_extension_is_rejected(session_factory, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    with session_factory() as session:
        with pytest.raises(UploadError) as error:
            asyncio.run(
                upload_service.save_upload(make_upload(make_docx(), "notes.pdf", PDF_MEDIA_TYPE), session)
            )

    assert error.value.status_code == 422
    assert list(tmp_path.iterdir()) == []
