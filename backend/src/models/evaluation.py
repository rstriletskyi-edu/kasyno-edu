from enum import StrEnum

from pydantic import BaseModel, Field, SecretStr

QUESTION_MAX_LENGTH = 4_000
EXPECTED_ANSWER_MAX_LENGTH = 4_000
USER_ANSWER_MAX_LENGTH = 20_000
EXPLANATION_MAX_LENGTH = 500
API_KEY_MAX_LENGTH = 512
PROVIDER_MAX_LENGTH = 32
MODEL_MAX_LENGTH = 128


class Verdict(StrEnum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class LlmSessionCreateRequest(BaseModel):
    api_key: SecretStr | None = Field(default=None, max_length=API_KEY_MAX_LENGTH)
    provider: str | None = Field(default=None, max_length=PROVIDER_MAX_LENGTH)
    model: str | None = Field(default=None, max_length=MODEL_MAX_LENGTH)


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
