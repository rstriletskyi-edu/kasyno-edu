import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langchain_core.language_models import BaseChatModel

from src.configs.settings import Settings
from src.models.evaluation import EvaluationRequest, EvaluationResult, LlmGrade, LlmSessionCreateRequest
from src.services.flashcard_service import FlashcardService
from src.services.llm.credits_factory import CreditsCalculator, build_credits_calculator
from src.services.llm.evaluation_graph import EvaluationState, build_evaluation_graph
from src.services.llm.llm_factory import build_chat_model, resolve_provider
from src.utils.exceptions import (
    AppError,
    LlmEvaluationError,
    LlmNotConfiguredError,
    LlmSessionNotFoundError,
    LlmTimeoutError,
)


@dataclass
class _LlmSession:
    uid: str
    provider: str
    model: str
    base_url: str | None
    expires_at: datetime
    api_key: str = field(repr=False)


class EvaluationService:
    def __init__(
        self,
        settings: Settings,
        flashcards: FlashcardService,
        model_factory: Callable[[Settings, str], BaseChatModel] | None = None,
        clock: Callable[[], datetime] | None = None,
        credits_calculator: CreditsCalculator | None = None,
    ) -> None:
        self._settings = settings
        self._flashcards = flashcards
        self._model_factory = model_factory or build_chat_model
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.__credits_calculator = credits_calculator or build_credits_calculator(
            settings.credits_engine
        )
        self._sessions: dict[str, _LlmSession] = {}

    def create_session(self, uid: str, payload: LlmSessionCreateRequest) -> str:
        api_key = payload.api_key.get_secret_value() if payload.api_key is not None else None
        resolved_key = self._resolve_key(api_key)
        provider = resolve_provider(self._resolve_choice(payload.provider, self._settings.llm_provider))
        model = self._resolve_choice(payload.model, self._settings.llm_model)
        base_url = self._resolve_base_url(payload.base_url)
        if provider == "ollama" and not base_url:
            raise LlmNotConfiguredError("Model URL is required for provider ollama")
        session_id = str(uuid4())
        self._sessions[session_id] = _LlmSession(
            uid=uid,
            api_key=resolved_key,
            provider=provider,
            model=model,
            base_url=base_url,
            expires_at=self._clock() + timedelta(seconds=self._settings.llm_session_ttl_seconds),
        )
        return session_id

    async def evaluate(
        self, uid: str, session_id: str, payload: EvaluationRequest
    ) -> EvaluationResult:
        session = self._require_session(uid, session_id)
        flashcard = self._flashcards.get_flashcard_by_id(payload.question_id)
        session_settings = self._settings.model_copy(
            update={
                "llm_provider": session.provider,
                "llm_model": session.model,
                "llm_base_url": session.base_url,
            }
        )
        graph = build_evaluation_graph(
            lambda: self._model_factory(session_settings, session.api_key),
            self._settings.llm_max_answer_chars,
        )
        try:
            state: EvaluationState = await asyncio.wait_for(
                graph.ainvoke(
                    {
                        "question": flashcard.question,
                        "expected_answer": flashcard.expected_answer,
                        "user_answer": payload.user_answer,
                        "result": None,
                    }
                ),
                timeout=self._settings.llm_timeout_seconds,
            )
        except TimeoutError as exc:
            raise LlmTimeoutError() from exc
        except AppError:
            raise
        except Exception as exc:
            raise LlmEvaluationError() from exc

        grade = state.get("result")
        if grade is None:
            raise LlmEvaluationError()
        if not isinstance(grade, LlmGrade):
            grade = LlmGrade.model_validate(grade)
        return EvaluationResult(
            score=grade.score,
            credits_received=self.__credits_calculator(grade.score),
            verdict=grade.verdict,
            explanation=grade.explanation,
        )

    def _resolve_key(self, api_key: str | None) -> str:
        candidate = (api_key or "").strip()
        if candidate:
            return candidate
        fallback = (self._settings.llm_api_key or "").strip()
        if fallback:
            return fallback
        raise LlmNotConfiguredError("LLM API key is not configured")

    def _resolve_choice(self, value: str | None, fallback: str) -> str:
        candidate = (value or "").strip()
        return candidate or fallback

    def _resolve_base_url(self, value: str | None) -> str | None:
        if value:
            return value
        fallback = (self._settings.llm_base_url or "").strip()
        return fallback or None

    def _require_session(self, uid: str, session_id: str) -> _LlmSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise LlmSessionNotFoundError()
        if session.expires_at <= self._clock():
            self._sessions.pop(session_id, None)
            raise LlmSessionNotFoundError()
        if session.uid != uid:
            raise LlmSessionNotFoundError()
        return session
