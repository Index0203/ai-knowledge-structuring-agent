from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from app.core.config import settings


def make_docx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<w:document />")
    return buffer.getvalue()


def test_upload_pdf_saves_validated_file(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("research.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "research.pdf"
    assert body["media_type"] == "application/pdf"
    assert (tmp_path / body["storage_key"]).read_bytes().startswith(b"%PDF-")


def test_upload_docx_accepts_openxml_document(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("notes.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 201
    assert response.json()["original_filename"] == "notes.docx"


def test_upload_rejects_unsupported_or_invalid_content(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    unsupported = client.post("/api/v1/uploads", files={"file": ("notes.txt", b"text", "text/plain")})
    disguised = client.post("/api/v1/uploads", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})

    assert unsupported.status_code == 415
    assert disguised.status_code == 422
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_file_larger_than_configured_limit(client, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_upload_size_bytes", 5)
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("large.pdf", b"%PDF-more-than-five-bytes", "application/pdf")},
    )

    assert response.status_code == 413
    assert list(tmp_path.iterdir()) == []


def test_upload_persists_a_document_row(client, db_session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    response = client.post(
        "/api/v1/uploads",
        files={"file": ("research.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )

    document_id = response.json()["document_id"]
    status_response = client.get(f"/api/v1/documents/{document_id}")

    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "uploaded"
    assert body["tree_status"] == "none"
    assert body["chunk_count"] == 0
