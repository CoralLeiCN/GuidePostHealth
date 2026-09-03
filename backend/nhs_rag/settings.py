from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from ``GUIDEPOST_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_prefix="GUIDEPOST_",
        extra="ignore",
    )

    app_name: str = "GuidePost Health"
    environment: str = "development"
    corpus_dir: Path = REPOSITORY_ROOT / "data" / "nhs"
    source_manifest: Path = REPOSITORY_ROOT / "config" / "nhs_sources.json"
    collection_name: str = "health_guidance"
    qdrant_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:6333")
    qdrant_timeout_seconds: int = Field(default=5, ge=1, le=60)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = Field(default=6, ge=1, le=20)
    maximum_evidence_chunks: int = Field(default=9, ge=1, le=20)
    codex_enabled: bool = True
    codex_model: str = "gpt-5.6-terra"
    codex_runtime_dir: Path = REPOSITORY_ROOT / ".codex-runtime"
    codex_timeout_seconds: float = Field(default=75.0, ge=5.0, le=300.0)
    codex_max_concurrency: int = Field(default=2, ge=1, le=8)
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
