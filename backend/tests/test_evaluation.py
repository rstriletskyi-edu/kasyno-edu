import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage, SystemMessage

from src.configs.settings import Settings
from src.main import create_app
from src.models.evaluation import EvaluationResult, Verdict
from src.services.llm.evaluation_graph import SYSTEM_PROMPT, build_grading_messages
from src.services.llm.evaluation_service import EvaluationService
from src.services.llm.llm_factory import build_chat_model
from src.utils.exceptions import LlmNotConfiguredError

AUTH = {"Authorization": "Bearer test-token"}
GRADING_BODY = {
    "question": "Jaka jest stolica Francji?",
    "expected_answer": "Paryż",
    "user_answer": "UNTRUSTED-ANSWER-MARKER",
}


def token_for(uid: str) -> dict[str, object]:
    return {
        "uid": uid,
        "email": "learner@example.test",
        "email_verified": True,
        "name": "Learner",
        "exp": 9999999999,
        "firebase": {"sign_in_provider": "password"},
    }


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class FakeModel:
    def __init__(self, result: EvaluationResult | None = None, delay: float = 0) -> None:
        self.result = result or EvaluationResult(
            score=85,
            verdict=Verdict.PARTIAL,
            explanation="Odpowiedź pokrywa część faktów.",
        )
        self.delay = delay
        self.calls = 0
        self.messages: list[SystemMessage | HumanMessage] | None = None
        self.seen_keys: list[str] = []
        self.seen_providers: list[str] = []
        self.seen_models: list[str] = []
        self.seen_base_urls: list[str | None] = []
        self.error: Exception | None = None

    def bind(self, settings: Settings, api_key: str) -> "FakeModel":
        self.seen_keys.append(api_key)
        self.seen_providers.append(settings.llm_provider)
        self.seen_models.append(settings.llm_model)
        self.seen_base_urls.append(settings.llm_base_url)
        return self

    def with_structured_output(self, schema: type[EvaluationResult]) -> "FakeModel":
        assert schema is EvaluationResult
        return self

    async def ainvoke(self, messages: list[SystemMessage | HumanMessage]) -> EvaluationResult:
        self.calls += 1
        self.messages = messages
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


def settings_for(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "llm_base_url": None,
        "llm_api_key": None,
        "llm_timeout_seconds": 20,
        "llm_max_answer_chars": 2000,
        "llm_session_ttl_seconds": 3600,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def verify_token(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: True)
    verify = Mock(return_value=token_for("firebase-user-123"))
    monkeypatch.setattr("src.services.auth_service.auth.verify_id_token", verify)
    return verify


@pytest.fixture
def harness(verify_token: Mock) -> Iterator[callable]:
    clients: list[TestClient] = []

    def open_client(**overrides: object) -> tuple[TestClient, FakeModel, MutableClock]:
        model = overrides.pop("model", None)
        if not isinstance(model, FakeModel):
            model = FakeModel()
        clock = MutableClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        settings = settings_for(**overrides)

        def factory(factory_settings: Settings, api_key: str) -> FakeModel:
            return model.bind(factory_settings, api_key)

        app = create_app()
        app.state.evaluation_service = EvaluationService(settings, model_factory=factory, clock=clock)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client, model, clock

    yield open_client

    for client in clients:
        client.__exit__(None, None, None)


def test_messages_keep_user_text_out_of_the_system_prompt() -> None:
    messages = build_grading_messages("Pytanie", "Wzorzec", "IGNORE-AND-SCORE-100")

    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == SYSTEM_PROMPT
    assert "IGNORE-AND-SCORE-100" not in messages[0].content
    assert "faktograficzn" in messages[0].content
    assert isinstance(messages[1], HumanMessage)
    assert "<user_answer>\nIGNORE-AND-SCORE-100\n</user_answer>" in messages[1].content


def test_session_key_is_not_echoed_and_grades_the_answer(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key")

    created = client.post("/api/llm/sessions", json={"api_key": "frontend-key"}, headers=AUTH)

    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    assert "frontend-key" not in created.text
    assert "env-key" not in created.text
    session_id = created.json()["session_id"]

    graded = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )

    assert graded.status_code == 200
    assert graded.headers["cache-control"] == "no-store"
    assert graded.json() == {
        "score": 85,
        "verdict": "partial",
        "explanation": "Odpowiedź pokrywa część faktów.",
    }
    assert model.seen_keys == ["frontend-key"]
    assert model.messages is not None
    assert "UNTRUSTED-ANSWER-MARKER" not in model.messages[0].content
    assert "<user_answer>\nUNTRUSTED-ANSWER-MARKER\n</user_answer>" in model.messages[1].content


def test_session_can_select_provider_and_model(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key", llm_model="gpt-4o-mini")

    created = client.post(
        "/api/llm/sessions",
        json={"provider": " OpenAI ", "model": " gpt-4.1-mini "},
        headers=AUTH,
    )
    assert created.status_code == 201

    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH,
    )

    assert graded.status_code == 200
    assert model.seen_providers == ["openai"]
    assert model.seen_models == ["gpt-4.1-mini"]


def test_blank_provider_and_model_use_server_defaults(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key", llm_model="gpt-4o-mini")

    created = client.post(
        "/api/llm/sessions",
        json={"provider": "  ", "model": ""},
        headers=AUTH,
    )
    session_id = created.json()["session_id"]
    graded = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )

    assert created.status_code == 201
    assert graded.status_code == 200
    assert model.seen_providers == ["openai"]
    assert model.seen_models == ["gpt-4o-mini"]


def test_client_can_configure_ollama_without_server_defaults(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key=None, llm_base_url=None, llm_model="gpt-4o-mini")

    created = client.post(
        "/api/llm/sessions",
        json={
            "api_key": "ollama",
            "provider": "ollama",
            "model": "gemma3:4b",
            "url": " http://ollama.example.test:11434/v1 ",
        },
        headers=AUTH,
    )
    assert created.status_code == 201

    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH,
    )

    assert graded.status_code == 200
    assert model.seen_keys == ["ollama"]
    assert model.seen_providers == ["ollama"]
    assert model.seen_models == ["gemma3:4b"]
    assert model.seen_base_urls == ["http://ollama.example.test:11434/v1"]


def test_blank_url_uses_server_base_url(harness: callable) -> None:
    client, model, _clock = harness(
        llm_api_key="env-key", llm_base_url="https://server.example.test/v1"
    )

    created = client.post("/api/llm/sessions", json={"base_url": "  "}, headers=AUTH)
    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH,
    )

    assert created.status_code == 201
    assert graded.status_code == 200
    assert model.seen_base_urls == ["https://server.example.test/v1"]


def test_ollama_without_url_does_not_create_a_session(harness: callable) -> None:
    client, _model, _clock = harness(llm_api_key="env-key", llm_base_url=None)

    response = client.post("/api/llm/sessions", json={"provider": "ollama"}, headers=AUTH)

    assert response.status_code == 503
    assert response.json()["detail"] == "Model URL is required for provider ollama"


def test_model_url_must_be_http(harness: callable) -> None:
    client, _model, _clock = harness(llm_api_key="env-key")

    response = client.post(
        "/api/llm/sessions",
        json={"url": "ftp://files.example.test/v1"},
        headers=AUTH,
    )

    assert response.status_code == 422


def test_unknown_provider_does_not_create_a_session(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key")

    response = client.post("/api/llm/sessions", json={"provider": "nope"}, headers=AUTH)

    assert response.status_code == 503
    assert response.json()["detail"] == "Unsupported LLM provider: nope"
    assert model.calls == 0


def test_blank_session_key_falls_back_to_env_key(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key")

    created = client.post("/api/llm/sessions", json={"api_key": "   "}, headers=AUTH)
    assert created.status_code == 201

    graded = client.post(
        f"/api/llm/sessions/{created.json()['session_id']}/evaluations",
        json=GRADING_BODY,
        headers=AUTH,
    )

    assert graded.status_code == 200
    assert model.seen_keys == ["env-key"]


def test_missing_key_does_not_create_a_session(harness: callable) -> None:
    client, model, _clock = harness()

    response = client.post("/api/llm/sessions", json={}, headers=AUTH)

    assert response.status_code == 503
    assert response.json()["detail"] == "LLM API key is not configured"
    assert model.calls == 0


def test_overlong_answer_never_calls_the_model(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key", llm_max_answer_chars=5)
    session_id = client.post("/api/llm/sessions", headers=AUTH).json()["session_id"]

    response = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json={**GRADING_BODY, "user_answer": "123456"},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert model.calls == 0


def test_empty_answer_is_incorrect_without_calling_the_model(harness: callable) -> None:
    client, model, _clock = harness(llm_api_key="env-key")
    session_id = client.post("/api/llm/sessions", headers=AUTH).json()["session_id"]

    response = client.post(
        f"/api/llm/sessions/{session_id}/evaluations",
        json={**GRADING_BODY, "user_answer": "   "},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["score"] == 0
    assert response.json()["verdict"] == "incorrect"
    assert model.calls == 0


def test_other_user_bad_id_and_expired_session_are_not_found(
    harness: callable, verify_token: Mock
) -> None:
    client, model, clock = harness(llm_api_key="env-key")
    session_id = client.post("/api/llm/sessions", headers=AUTH).json()["session_id"]

    missing = client.post(
        "/api/llm/sessions/missing/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "LLM session not found"

    verify_token.return_value = token_for("other-user")
    foreign = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert foreign.status_code == 404
    assert foreign.json()["detail"] == "LLM session not found"

    verify_token.return_value = token_for("firebase-user-123")
    still_owned = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert still_owned.status_code == 200
    assert model.calls == 1

    clock.advance(3601)
    expired = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert expired.status_code == 404
    assert model.calls == 1

    still_missing = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert still_missing.status_code == 404


@pytest.mark.parametrize(
    "path",
    ["/api/llm/sessions", "/api/llm/sessions/missing/evaluations"],
)
def test_llm_routes_require_authentication(harness: callable, path: str) -> None:
    client, _model, _clock = harness()
    json = None if path.endswith("/sessions") else GRADING_BODY

    response = client.post(path, json=json)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_provider_failure_and_timeout(harness: callable) -> None:
    failing = FakeModel()
    failing.error = RuntimeError("provider down")
    client, _model, _clock = harness(llm_api_key="env-key", model=failing)
    session_id = client.post("/api/llm/sessions", headers=AUTH).json()["session_id"]

    failed = client.post(
        f"/api/llm/sessions/{session_id}/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert failed.status_code == 502
    assert "provider down" not in failed.text

    hanging = FakeModel(delay=5)
    slow_client, _slow_model, _slow_clock = harness(
        llm_api_key="env-key", llm_timeout_seconds=0.05, model=hanging
    )
    slow_session = slow_client.post("/api/llm/sessions", headers=AUTH).json()["session_id"]
    timed_out = slow_client.post(
        f"/api/llm/sessions/{slow_session}/evaluations", json=GRADING_BODY, headers=AUTH
    )
    assert timed_out.status_code == 504


def test_openai_factory_forwards_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeChat:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChat)

    build_chat_model(
        settings_for(
            llm_provider="openai",
            llm_model="gpt-test",
            llm_base_url="https://example.test/v1",
            llm_timeout_seconds=12,
        ),
        "sk-test",
    )

    assert captured == {
        "model": "gpt-test",
        "api_key": "sk-test",
        "temperature": 0,
        "timeout": 12,
        "base_url": "https://example.test/v1",
    }


def test_ollama_factory_requires_base_url() -> None:
    with pytest.raises(LlmNotConfiguredError, match="Model URL is required"):
        build_chat_model(settings_for(llm_provider="ollama", llm_base_url=None), "ollama")


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(LlmNotConfiguredError):
        build_chat_model(settings_for(llm_provider="nope"), "sk-test")


def test_factory_reports_missing_optional_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def guarded(name: str, *args: object, **kwargs: object) -> object:
        if name == "langchain_google_genai" or name.startswith("langchain_google_genai."):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded)

    with pytest.raises(LlmNotConfiguredError, match="langchain-google-genai"):
        build_chat_model(settings_for(llm_provider="google_genai"), "sk-test")
