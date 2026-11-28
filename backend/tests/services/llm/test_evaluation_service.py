from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import Mock

from google.api_core.exceptions import PermissionDenied
import pytest

from src.configs.settings import Settings
from src.models.evaluation import EvaluationRequest, LlmGrade, Verdict
from src.services.llm.evaluation_service import EvaluationService
from src.services.user_service import UserService
from src.utils.exceptions import FirebaseNotInitializedError, ProfileUnavailableError
from tests.fakes.auth import DEFAULT_UID, make_user
from tests.fakes.firestore import FakeFirestoreDB
from tests.fakes.llm import FakeFlashcards, FakeModel, MutableClock


def _build_service(
    make_settings: Callable[..., Settings],
    *,
    user_service: UserService | None = None,
    model: FakeModel | None = None,
) -> EvaluationService:
    resolved_model = model or FakeModel()
    settings = make_settings(llm_api_key="env-key")
    clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    return EvaluationService(
        settings,
        FakeFlashcards(),  # type: ignore[arg-type]
        user_service=user_service,
        model_factory=lambda s, key: resolved_model.bind(s, key),  # type: ignore[arg-type]
        clock=clock,
    )


@pytest.mark.anyio
async def test_evaluate_calls_user_service_add_credits_with_reason(
    make_settings: Callable[..., Settings],
) -> None:
    user_service = Mock(spec=UserService)
    service = _build_service(make_settings, user_service=user_service)
    user = make_user()
    session_id = service.create_session(user.uid, payload=_session_payload())

    result = await service.evaluate(
        user,
        session_id,
        EvaluationRequest(question_id="card-1", user_answer="Paryż"),
    )

    assert result.credits_received == 8
    user_service.add_credits.assert_called_once_with(
        user, 8, EvaluationService.CREDITS_REASON
    )


@pytest.mark.anyio
async def test_evaluate_does_not_call_add_credits_when_zero_credits(
    make_settings: Callable[..., Settings],
) -> None:
    user_service = Mock(spec=UserService)
    model = FakeModel(
        result=LlmGrade(
            score=9,
            verdict=Verdict.INCORRECT,
            explanation="Brak kluczowych informacji.",
        )
    )
    service = _build_service(make_settings, user_service=user_service, model=model)
    user = make_user()
    session_id = service.create_session(user.uid, payload=_session_payload())

    result = await service.evaluate(
        user,
        session_id,
        EvaluationRequest(question_id="card-1", user_answer="Nie wiem"),
    )

    assert result.credits_received == 0
    user_service.add_credits.assert_not_called()


@pytest.mark.anyio
async def test_evaluate_propagates_profile_unavailable_without_wrapping(
    make_settings: Callable[..., Settings],
) -> None:
    db = FakeFirestoreDB(get_error=PermissionDenied("firestore denied"))
    service = _build_service(make_settings, user_service=UserService(db))  # type: ignore[arg-type]
    user = make_user()
    session_id = service.create_session(user.uid, payload=_session_payload())

    with pytest.raises(ProfileUnavailableError):
        await service.evaluate(
            user,
            session_id,
            EvaluationRequest(question_id="card-1", user_answer="Paryż"),
        )


@pytest.mark.anyio
async def test_evaluate_without_injected_user_service_resolves_firestore_lazily(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeFirestoreDB(credits=100)
    monkeypatch.setattr("src.services.llm.evaluation_service.get_firestore", lambda: db)
    service = _build_service(make_settings, user_service=None)
    user = make_user(DEFAULT_UID)
    session_id = service.create_session(user.uid, payload=_session_payload())

    result = await service.evaluate(
        user,
        session_id,
        EvaluationRequest(question_id="card-1", user_answer="Paryż"),
    )

    assert result.credits_received == 8
    assert db.state["credits"] == 108.0
    assert db.state["transactions"][0][1]["Reason"] == EvaluationService.CREDITS_REASON


@pytest.mark.anyio
async def test_evaluate_without_injected_user_service_raises_when_firebase_uninitialized(
    make_settings: Callable[..., Settings],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.firebase_service.is_firebase_initialized", lambda: False)
    service = _build_service(make_settings, user_service=None)
    user = make_user()
    session_id = service.create_session(user.uid, payload=_session_payload())

    with pytest.raises(FirebaseNotInitializedError):
        await service.evaluate(
            user,
            session_id,
            EvaluationRequest(question_id="card-1", user_answer="Paryż"),
        )


def _session_payload():
    from src.models.evaluation import LlmSessionCreateRequest

    return LlmSessionCreateRequest()
