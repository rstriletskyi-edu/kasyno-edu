from enum import StrEnum
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator

QUESTION_MAX_LENGTH = 4_000
EXPECTED_ANSWER_MAX_LENGTH = 4_000
USER_ANSWER_MAX_LENGTH = 20_000
EXPLANATION_MAX_LENGTH = 500
API_KEY_MAX_LENGTH = 512
PROVIDER_MAX_LENGTH = 32
MODEL_MAX_LENGTH = 128
BASE_URL_MAX_LENGTH = 512


class Verdict(StrEnum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class LlmSessionCreateRequest(BaseModel):
    api_key: SecretStr | None = Field(default=None, max_length=API_KEY_MAX_LENGTH)
    provider: str | None = Field(default=None, max_length=PROVIDER_MAX_LENGTH)
    model: str | None = Field(default=None, max_length=MODEL_MAX_LENGTH)
    base_url: str | None = Field(
        default=None,
        max_length=BASE_URL_MAX_LENGTH,
        validation_alias=AliasChoices("base_url", "url"),
    )

    @field_validator("base_url", mode="before")
    @classmethod
    def blank_base_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("base_url")
    @classmethod
    def http_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        parsed = urlparse(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Model URL must be an http or https URL")
        return stripped


class LlmSessionResponse(BaseModel):
    session_id: str


class EvaluationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=QUESTION_MAX_LENGTH)
    expected_answer: str = Field(min_length=1, max_length=EXPECTED_ANSWER_MAX_LENGTH)
    user_answer: str = Field(max_length=USER_ANSWER_MAX_LENGTH)


class EvaluationResult(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: Verdict
    explanation: str = Field(min_length=1, max_length=EXPLANATION_MAX_LENGTH)
