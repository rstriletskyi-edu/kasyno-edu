import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langchain_core.language_models import BaseChatModel

from src.configs.settings import Settings
from src.models.evaluation import EvaluationRequest, EvaluationResult
from src.services.evaluation_graph import EvaluationState, build_evaluation_graph
from src.services.llm_factory import build_chat_model
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
    api_key: str = field(repr=False)
    expires_at: datetime


class EvaluationService:
    def __init__(
        self,
        settings: Settings,
        model_factory: Callable[[Settings, str], BaseChatModel] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._model_factory = model_factory or build_chat_model
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[str, _LlmSession] = {}

    def create_session(self, uid: str, api_key: str | None) -> str:
        resolved = self._resolve_key(api_key)
        session_id = str(uuid4())
        self._sessions[session_id] = _LlmSession(
            uid=uid,
            api_key=resolved,
            expires_at=self._clock() + timedelta(seconds=self._settings.llm_session_ttl_seconds),
        )
        return session_id

    async def evaluate(
        self, uid: str, session_id: str, payload: EvaluationRequest
    ) -> EvaluationResult:
        session = self._require_session(uid, session_id)
        graph = build_evaluation_graph(
            lambda: self._model_factory(self._settings, session.api_key),
            self._settings.llm_max_answer_chars,
        )
        try:
            state: EvaluationState = await asyncio.wait_for(
                graph.ainvoke(
                    {
                        "question": payload.question,
                        "expected_answer": payload.expected_answer,
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

        result = state.get("result")
        if isinstance(result, EvaluationResult):
            return result
        if result is None:
            raise LlmEvaluationError()
        return EvaluationResult.model_validate(result)

    def _resolve_key(self, api_key: str | None) -> str:
        candidate = (api_key or "").strip()
        if candidate:
            return candidate
        fallback = (self._settings.llm_api_key or "").strip()
        if fallback:
            return fallback
        raise LlmNotConfiguredError("LLM API key is not configured")

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
