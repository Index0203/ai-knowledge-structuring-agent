"""OCR engine selection: availability, settings and graceful degradation."""

from app.core.config import settings
from app.pipelines.document_processing.ocr import (
    TesseractOcrEngine,
    create_ocr_engine,
    ocr_text_score,
)


def test_engine_is_disabled_by_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", False)

    assert create_ocr_engine() is None


def test_engine_is_none_when_the_binary_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr("app.pipelines.document_processing.ocr.shutil.which", lambda _binary: None)

    assert create_ocr_engine() is None


def test_engine_is_built_when_the_binary_exists(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ocr_enabled", True)
    monkeypatch.setattr(settings, "ocr_languages", "chi_sim+eng")
    monkeypatch.setattr(settings, "ocr_psm", 3)
    monkeypatch.setattr("app.pipelines.document_processing.ocr.shutil.which", lambda _binary: "/usr/bin/tesseract")

    engine = create_ocr_engine()

    assert isinstance(engine, TesseractOcrEngine)
    assert engine.is_available() is True


def test_tesseract_engine_reports_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr("app.pipelines.document_processing.ocr.shutil.which", lambda _binary: None)

    assert TesseractOcrEngine("eng").is_available() is False


def test_score_ranks_structure_over_extra_characters() -> None:
    structured = "第二章 数智聚焦\n一、数字化知识库构建\n二、联合研发"
    flat = "这是一段没有章节标记的长文本。" * 30

    assert ocr_text_score(structured) > ocr_text_score(flat)
