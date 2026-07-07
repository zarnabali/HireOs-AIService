from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    ai_service_api_key: str = Field(default="", alias="AI_SERVICE_API_KEY")
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )

    document_extractor_root: str = Field(
        default="Agentic-Document-Extraction-PDF",
        alias="DOCUMENT_EXTRACTOR_ROOT",
    )
    document_extractor_enabled: bool = Field(
        default=True,
        alias="DOCUMENT_EXTRACTOR_ENABLED",
    )
    document_extractor_provider: str = Field(
        default="openai",
        alias="DOCUMENT_EXTRACTOR_PROVIDER",
    )
    document_extractor_dpi: int = Field(default=200, alias="DOCUMENT_EXTRACTOR_DPI")
    document_extractor_max_image_dimension: int = Field(
        default=2048,
        alias="DOCUMENT_EXTRACTOR_MAX_IMAGE_DIMENSION",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def service_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def resolved_document_extractor_root(self) -> Path:
        root = Path(self.document_extractor_root)
        if not root.is_absolute():
            root = self.service_root / root
        return root.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
