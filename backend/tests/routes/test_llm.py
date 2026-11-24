from collections.abc import Callable
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from src.configs.settings import Settings
from src.dependencies import get_evaluation_service
from src.services.llm.evaluation_service import EvaluationService
from tests.fakes.auth import AUTH_HEADERS, DEFAULT_UID, make_token_claims
from tests.fakes.llm import (
    CARD_ANSWER,
    CARD_QUESTION,
    GRADING_BODY,
    FakeFlashcards,
    FakeModel,
    MutableClock,
)


@pytest.fixture
def llm_client(
    make_client: Callable[..., TestClient],
    make_settings: Callable[..., Settings],
    verify_token: Mock,
) -> Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]]:
    def _open(**overrides: object) -> tuple[TestClient, EvaluationService, FakeModel, MutableClock]:
        model = overrides.pop("model", None)
        if not isinstance(model, FakeModel):
            model = FakeModel()
        clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        settings = make_settings(**overrides)

        def factory(factory_settings: Settings, api_key: str) -> FakeModel:
            return model.bind(factory_settings, api_key)

        service = EvaluationService(
            settings,
            FakeFlashcards(),  # type: ignore[arg-type]
            model_factory=factory,  # type: ignore[arg-type]
            clock=clock,
        )
        client = make_client(
            dependency_overrides={get_evaluation_service: lambda: service}
        )
        return client, service, model, clock

    return _open


def test_session_key_is_not_echoed_and_grades_the_answer(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key")

    created = client.post(
        "/api/llm/sessions", json={"api_key": "frontend-key"}, headers=AUTH_HEADERS
    )

    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    assert "frontend-key" not in created.text
    assert "env-key" not in created.text
    session_id = created.json()["session_id"]

    graded = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )

    assert graded.status_code == 200
    assert graded.headers["cache-control"] == "no-store"
    assert graded.json() == {
        "score": 85,
        "credits_received": 8,
        "verdict": "partial",
        "explanation": "Odpowiedź pokrywa część faktów.",
    }
    assert model.seen_keys == ["frontend-key"]
    assert model.messages is not None
    assert "UNTRUSTED-ANSWER-MARKER" not in model.messages[0].content
    assert f"<question>\n{CARD_QUESTION}\n</question>" in model.messages[1].content
    assert f"<expected_answer>\n{CARD_ANSWER}\n</expected_answer>" in model.messages[1].content
    assert "<user_answer>\nUNTRUSTED-ANSWER-MARKER\n</user_answer>" in model.messages[1].content


def test_session_can_select_provider_and_model(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key", llm_model="gpt-4o-mini")

    created = client.post(
        "/api/llm/sessions",
        json={"provider": " OpenAI ", "model": " gpt-4.1-mini "},
        headers=AUTH_HEADERS,
    )
    assert created.status_code == 201

    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )

    assert graded.status_code == 200
    assert model.seen_providers == ["openai"]
    assert model.seen_models == ["gpt-4.1-mini"]


def test_blank_provider_and_model_use_server_defaults(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key", llm_model="gpt-4o-mini")

    created = client.post(
        "/api/llm/sessions",
        json={"provider": "  ", "model": ""},
        headers=AUTH_HEADERS,
    )
    session_id = created.json()["session_id"]
    graded = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )

    assert created.status_code == 201
    assert graded.status_code == 200
    assert model.seen_providers == ["openai"]
    assert model.seen_models == ["gpt-4o-mini"]


def test_client_can_configure_ollama_without_server_defaults(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(
        llm_api_key=None, llm_base_url=None, llm_model="gpt-4o-mini"
    )

    created = client.post(
        "/api/llm/sessions",
        json={
            "api_key": "ollama",
            "provider": "ollama",
            "model": "gemma3:4b",
            "url": " http://ollama.example.test:11434/v1 ",
        },
        headers=AUTH_HEADERS,
    )
    assert created.status_code == 201

    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )

    assert graded.status_code == 200
    assert model.seen_keys == ["ollama"]
    assert model.seen_providers == ["ollama"]
    assert model.seen_models == ["gemma3:4b"]
    assert model.seen_base_urls == ["http://ollama.example.test:11434/v1"]


def test_blank_url_uses_server_base_url(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(
        llm_api_key="env-key", llm_base_url="https://server.example.test/v1"
    )

    created = client.post("/api/llm/sessions", json={"base_url": "  "}, headers=AUTH_HEADERS)
    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )

    assert created.status_code == 201
    assert graded.status_code == 200
    assert model.seen_base_urls == ["https://server.example.test/v1"]


def test_ollama_without_url_does_not_create_a_session(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, _model, _clock = llm_client(llm_api_key="env-key", llm_base_url=None)

    response = client.post(
        "/api/llm/sessions", json={"provider": "ollama"}, headers=AUTH_HEADERS
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Model URL is required for provider ollama"


def test_model_url_must_be_http(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, _model, _clock = llm_client(llm_api_key="env-key")

    response = client.post(
        "/api/llm/sessions",
        json={"url": "ftp://files.example.test/v1"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422


def test_unknown_provider_does_not_create_a_session(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key")

    response = client.post("/api/llm/sessions", json={"provider": "nope"}, headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == "Unsupported LLM provider: nope"
    assert model.calls == 0


def test_blank_session_key_falls_back_to_env_key(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key")

    created = client.post("/api/llm/sessions", json={"api_key": "   "}, headers=AUTH_HEADERS)
    assert created.status_code == 201

    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )

    assert graded.status_code == 200
    assert model.seen_keys == ["env-key"]


def test_missing_key_does_not_create_a_session(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client()

    response = client.post("/api/llm/sessions", json={}, headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"] == "LLM API key is not configured"
    assert model.calls == 0


def test_overlong_answer_never_calls_the_model(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key", llm_max_answer_chars=5)
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    response = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json={**GRADING_BODY, "user_answer": "123456"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
    assert model.calls == 0


def test_empty_answer_is_incorrect_without_calling_the_model(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key")
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    response = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json={**GRADING_BODY, "user_answer": "   "},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["score"] == 0
    assert response.json()["credits_received"] == 0
    assert response.json()["verdict"] == "incorrect"
    assert model.calls == 0


def test_missing_flashcard_does_not_call_the_model(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(llm_api_key="env-key")
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    response = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json={**GRADING_BODY, "question_id": "missing"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404
    assert model.calls == 0


def test_other_user_bad_id_and_expired_session_are_not_found(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
    verify_token: Mock,
) -> None:
    client, _service, model, clock = llm_client(llm_api_key="env-key")
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    missing = client.post(
        "/api/llm/sessions/missing/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "LLM session not found"

    verify_token.return_value = make_token_claims("other-user")
    foreign = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "LLM session not found"

    verify_token.return_value = make_token_claims(DEFAULT_UID)
    still_owned = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert still_owned.status_code == 200
    assert model.calls == 1

    clock.advance(3601)
    expired = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert expired.status_code == 404
    assert model.calls == 1

    still_missing = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert still_missing.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", "/api/llm/sessions", None),
        ("GET", "/api/llm/sessions/missing", None),
        ("POST", "/api/llm/sessions/missing/evaluations", GRADING_BODY),
    ],
)
def test_llm_routes_require_authentication(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    client, _service, _model, _clock = llm_client()

    response = client.request(method, path, json=json_body)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_provider_failure_and_timeout(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    failing = FakeModel()
    failing.error = RuntimeError("provider down")
    client, _service, _model, _clock = llm_client(llm_api_key="env-key", model=failing)
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    failed = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert failed.status_code == 502
    assert "provider down" not in failed.text

    hanging = FakeModel(delay=5)
    slow_client, _slow_service, _slow_model, _slow_clock = llm_client(
        llm_api_key="env-key", llm_timeout_seconds=0.05, model=hanging
    )
    slow_session = slow_client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]
    timed_out = slow_client.post(
        f"/api/llm/sessions/{slow_session}/evaluations", json=GRADING_BODY, headers=AUTH_HEADERS
    )
    assert timed_out.status_code == 504


def test_verify_session_enforces_ownership_and_expiration(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
    verify_token: Mock,
) -> None:
    client, _service, _model, clock = llm_client(llm_api_key="env-key")
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    verified = client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS)
    assert verified.status_code == 200
    assert verified.headers["cache-control"] == "no-store"
    assert verified.json() == {"session_id": session_id}

    missing = client.get("/api/llm/sessions/missing", headers=AUTH_HEADERS)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "LLM session not found"

    verify_token.return_value = make_token_claims("other-user")
    foreign = client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS)
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "LLM session not found"

    verify_token.return_value = make_token_claims(DEFAULT_UID)
    still_owned = client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS)
    assert still_owned.status_code == 200

    clock.advance(3601)
    expired = client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS)
    assert expired.status_code == 404


def test_create_session_caps_sessions_per_user_and_purges_expired(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
    verify_token: Mock,
) -> None:
    client, service, _model, clock = llm_client(
        llm_api_key="env-key", llm_max_sessions_per_user=2
    )

    verify_token.return_value = make_token_claims("other-user")
    other_session = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    verify_token.return_value = make_token_claims(DEFAULT_UID)
    first = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]
    second = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    failed = client.post("/api/llm/sessions", json={"provider": "nope"}, headers=AUTH_HEADERS)
    assert failed.status_code == 503
    assert client.get(f"/api/llm/sessions/{first}", headers=AUTH_HEADERS).status_code == 200
    assert client.get(f"/api/llm/sessions/{second}", headers=AUTH_HEADERS).status_code == 200

    third = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]
    assert client.get(f"/api/llm/sessions/{first}", headers=AUTH_HEADERS).status_code == 404
    assert client.get(f"/api/llm/sessions/{second}", headers=AUTH_HEADERS).status_code == 200
    assert client.get(f"/api/llm/sessions/{third}", headers=AUTH_HEADERS).status_code == 200

    verify_token.return_value = make_token_claims("other-user")
    assert client.get(f"/api/llm/sessions/{other_session}", headers=AUTH_HEADERS).status_code == 200

    clock.advance(3601)
    verify_token.return_value = make_token_claims(DEFAULT_UID)
    fresh = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]
    assert list(service._sessions.keys()) == [fresh]


def test_create_session_rate_limit_is_scoped_per_user_and_resets_after_window(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
    verify_token: Mock,
) -> None:
    client, _service, _model, clock = llm_client(
        llm_api_key="env-key",
        llm_session_rate_limit_max=2,
        llm_rate_limit_window_seconds=60,
    )

    assert client.post("/api/llm/sessions", headers=AUTH_HEADERS).status_code == 201
    assert client.post("/api/llm/sessions", headers=AUTH_HEADERS).status_code == 201

    limited = client.post("/api/llm/sessions", headers=AUTH_HEADERS)
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"

    verify_token.return_value = make_token_claims("other-user")
    assert client.post("/api/llm/sessions", headers=AUTH_HEADERS).status_code == 201

    clock.advance(60)
    verify_token.return_value = make_token_claims(DEFAULT_UID)
    assert client.post("/api/llm/sessions", headers=AUTH_HEADERS).status_code == 201


def test_verify_session_rate_limit_returns_429(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, _model, _clock = llm_client(
        llm_api_key="env-key",
        llm_verify_rate_limit_max=2,
        llm_rate_limit_window_seconds=60,
    )
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    assert client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS).status_code == 200
    assert client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS).status_code == 200

    limited = client.get(f"/api/llm/sessions/{session_id}", headers=AUTH_HEADERS)
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


def test_evaluate_rate_limit_blocks_before_calling_model(
    llm_client: Callable[..., tuple[TestClient, EvaluationService, FakeModel, MutableClock]],
) -> None:
    client, _service, model, _clock = llm_client(
        llm_api_key="env-key",
        llm_eval_rate_limit_max=2,
        llm_rate_limit_window_seconds=60,
    )
    session_id = client.post("/api/llm/sessions", headers=AUTH_HEADERS).json()["session_id"]

    assert (
        client.post(
            f"/api/llm/sessions/{session_id}/evaluations",
            json=GRADING_BODY,
            headers=AUTH_HEADERS,
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/llm/sessions/{session_id}/evaluations",
            json=GRADING_BODY,
            headers=AUTH_HEADERS,
        ).status_code
        == 200
    )

    limited = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json=GRADING_BODY,
        headers=AUTH_HEADERS,
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"
    assert model.calls == 2
