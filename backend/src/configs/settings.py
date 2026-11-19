from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Kasyno Edu API"
    environment: str = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]

    firebase_credentials_path: Path = Path("credentials/firebase-service-account.json")
    firebase_project_id: str | None = None
    firebase_database_url: str
    questions_path: str

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_timeout_seconds: float = Field(default=20, gt=0)
    llm_max_answer_chars: int = Field(default=2000, gt=0)
    llm_session_ttl_seconds: int = Field(default=3600, gt=0)

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            return "openai"
        return value.strip().lower()

    @field_validator("llm_model", mode="before")
    @classmethod
    def normalize_model(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            return "gpt-4o-mini"
        return value.strip()

    @field_validator("llm_base_url", "llm_api_key", mode="before")
    @classmethod
    def blank_optional(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("firebase_database_url", "questions_path", mode="before")
    @classmethod
    def require_non_blank(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()

    @property
    def firebase_credentials_file(self) -> Path:
        path = self.firebase_credentials_path
        return path if path.is_absolute() else BASE_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
