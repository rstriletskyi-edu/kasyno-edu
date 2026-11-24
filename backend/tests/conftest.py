from collections.abc import Callable, Iterator
from contextlib import ExitStack
import os
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

# Settings are built when src.main is imported, which happens during collection,
# before fixtures run. These stand-ins satisfy the required fields without a project.
os.environ["FIREBASE_DATABASE_URL"] = "https://test.firebasedatabase.app"
os.environ["QUESTIONS_PATH"] = "questions"

from src.configs.settings import Settings
from src.main import create_app
from tests.fakes.auth import AUTH_HEADERS, make_token_claims
from tests.fakes.firestore import FakeFirestoreDB


@pytest.fixture(autouse=True)
def mock_firebase(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    if "allow_init_firebase" not in request.keywords:
        monkeypatch.setattr("src.services.firebase_service.init_firebase", lambda settings: False)


@pytest.fixture
def verify_token(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: True)
    verify = Mock(return_value=make_token_claims())
    monkeypatch.setattr("src.services.auth_service.auth.verify_id_token", verify)
    return verify


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return dict(AUTH_HEADERS)


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    def _build(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_base_url": None,
            "llm_api_key": None,
            "llm_timeout_seconds": 20,
            "llm_max_answer_chars": 2000,
            "llm_session_ttl_seconds": 3600,
            "firebase_database_url": "https://test.firebasedatabase.app",
            "questions_path": "questions",
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return _build


@pytest.fixture
def make_firestore_db() -> Callable[..., FakeFirestoreDB]:
    def _build(**kwargs: object) -> FakeFirestoreDB:
        return FakeFirestoreDB(**kwargs)  # type: ignore[arg-type]

    return _build


@pytest.fixture
def firestore_db(make_firestore_db: Callable[..., FakeFirestoreDB]) -> FakeFirestoreDB:
    return make_firestore_db()


@pytest.fixture
def make_client() -> Iterator[Callable[..., TestClient]]:
    with ExitStack() as stack:
        def _open(
            *,
            dependency_overrides: dict[object, Callable[..., object]] | None = None,
            state_overrides: dict[str, object] | None = None,
            rate_limit_max: int = 100,
            rate_limit_window: int = 60,
            configure_app: Callable[[FastAPI], None] | None = None,
        ) -> TestClient:
            app = create_app(rate_limit_max=rate_limit_max, rate_limit_window=rate_limit_window)
            if dependency_overrides:
                app.dependency_overrides.update(dependency_overrides)
            if state_overrides:
                for key, value in state_overrides.items():
                    setattr(app.state, key, value)
            if configure_app is not None:
                configure_app(app)
            return stack.enter_context(TestClient(app))

        yield _open


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()
