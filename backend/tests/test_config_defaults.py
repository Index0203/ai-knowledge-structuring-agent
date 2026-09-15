"""Guard rails for the defaults the deployment depends on."""

from app.core.config import Settings


def clean_settings(**overrides) -> Settings:
    """Defaults without the ambient .env / process environment of the deployment."""
    parameters: dict[str, object] = {
        "_env_file": None,
        "openai_api_key": None,
        "openai_model": None,
        "openai_base_url": None,
    }
    parameters.update(overrides)
    return Settings(**parameters)


def test_settings_defaults_match_the_documented_baseline() -> None:
    settings = clean_settings()

    assert settings.embedding_provider == "deterministic"
    assert settings.embedding_dimensions == 256
    assert settings.chroma_collection == "document_chunks"
    assert settings.structured_output_method == "auto"
    assert settings.chat_model_configured is False


def test_retrieval_defaults_are_sane() -> None:
    settings = clean_settings()

    assert settings.retrieval_top_k > 0
    assert 0.0 <= settings.retrieval_min_score <= 1.0
    assert settings.retrieval_candidate_multiplier >= 1
    assert settings.node_evidence_boost >= 0
    assert settings.chunk_max_characters > settings.chunk_overlap_characters >= 0


def test_ocr_defaults_match_the_tuned_values() -> None:
    settings = clean_settings()

    assert settings.ocr_enabled is True
    assert settings.ocr_dpi == 300
    assert settings.ocr_fallback_dpi == 200
    assert settings.ocr_psm == 3
    assert settings.ocr_binarize is False
    assert settings.ocr_max_pages > 0


def test_chat_model_requires_both_key_and_model() -> None:
    incomplete = clean_settings(openai_api_key="sk-test")

    assert incomplete.chat_model_configured is False


def test_chat_model_is_configured_when_key_and_model_are_present() -> None:
    complete = clean_settings(openai_api_key="sk-test", openai_model="deepseek-chat")

    assert complete.chat_model_configured is True
