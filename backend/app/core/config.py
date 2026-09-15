from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-knowledge-structuring-agent"
    app_env: str = "development"
    log_level: str = "INFO"
    backend_cors_origins: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://app:app@postgres:5432/knowledge_agent"
    redis_url: str = "redis://redis:6379/0"
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "document_chunks"
    upload_dir: str = "data/uploads"
    max_upload_size_bytes: int = 25 * 1024 * 1024

    # AI provider. Any OpenAI-compatible chat endpoint works via openai_base_url.
    openai_api_key: str | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    # auto | json_schema | function_calling | json_mode
    structured_output_method: str = "auto"

    # Embeddings. "deterministic" keeps the pipeline runnable without an API key.
    embedding_provider: str = "deterministic"
    embedding_dimensions: int = 256
    openai_embedding_model: str | None = None

    # Chunking and retrieval tuning.
    chunk_max_characters: int = 900
    chunk_overlap_characters: int = 150
    retrieval_top_k: int = 5
    retrieval_candidate_multiplier: int = 3
    retrieval_min_score: float = 0.1
    node_evidence_boost: float = 0.15
    max_question_characters: int = 1000

    # Async job reliability.
    task_max_retries: int = 2
    task_retry_backoff_seconds: int = 10
    task_retry_backoff_max_seconds: int = 120
    llm_request_timeout_seconds: int = 60
    llm_max_retries: int = 1
    stale_job_timeout_seconds: int = 1800
    reaper_interval_seconds: int = 300

    # OCR fallback for scanned PDFs.
    ocr_enabled: bool = True
    ocr_languages: str = "chi_sim+eng"
    ocr_dpi: int = 300
    ocr_fallback_dpi: int | None = 200
    ocr_psm: int = 3
    ocr_binarize: bool = False
    ocr_binarize_threshold: int = 165
    ocr_min_text_characters: int = 12
    ocr_max_pages: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def chat_model_configured(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)


settings = Settings()
