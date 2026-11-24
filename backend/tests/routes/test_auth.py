from collections.abc import Callable
from unittest.mock import Mock

from fastapi.testclient import TestClient
from google.api_core.exceptions import PermissionDenied as FirestorePermissionDenied
from google.cloud.firestore import SERVER_TIMESTAMP
import pytest

from src.dependencies import get_user_service
from src.services.user_service import UserService
from tests.fakes.auth import AUTH_HEADERS, DEFAULT_UID, INVALID_AUTH_HEADERS, UNSAFE_UIDS
from tests.fakes.firestore import FakeFirestoreDB


@pytest.fixture
def auth_client(
    make_client: Callable[..., TestClient],
    make_firestore_db: Callable[..., FakeFirestoreDB],
    verify_token: Mock,
) -> Callable[..., tuple[TestClient, FakeFirestoreDB]]:
    def _open(**db_kwargs: object) -> tuple[TestClient, FakeFirestoreDB]:
        db = make_firestore_db(**db_kwargs)
        client = make_client(
            dependency_overrides={get_user_service: lambda: UserService(db)}
        )
        return client, db

    return _open


def test_me_reads_only_token_uid_and_does_not_overwrite_existing_profile(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = auth_client(credits=0, extra_fields={"tokens": 999})

    response = client.get("/api/auth/me?uid=someone-else", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "uid": DEFAULT_UID,
        "email": "learner@example.test",
        "email_verified": True,
        "display_name": "Learner",
        "profile": {"created_at": "2026-11-12T00:00:00Z", "credits": 0},
    }
    assert db.seen_uids == [DEFAULT_UID]
    assert db.user_doc.create_calls == []
    assert db.user_doc.set_calls == []


def test_me_without_profile_returns_503_and_never_creates(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = auth_client(exists=False)

    response = client.get("/api/auth/me", headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}
    assert db.user_doc.create_calls == []
    assert db.user_doc.set_calls == []
    assert db.user_doc.update_calls == []


@pytest.mark.parametrize("authorization", INVALID_AUTH_HEADERS)
def test_register_requires_bearer_token(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    authorization: str | None,
) -> None:
    client, _db = auth_client(exists=False)
    headers = {"Authorization": authorization} if authorization is not None else {}
    response = client.post("/api/auth/register", headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    verify_token.assert_not_called()


def test_register_creates_missing_profile(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = auth_client(exists=False)

    response = client.post("/api/auth/register", headers=AUTH_HEADERS)

    assert response.status_code == 201
    assert response.json()["uid"] == DEFAULT_UID
    assert db.user_doc.create_calls == [{"created_at": SERVER_TIMESTAMP, "credits": 0}]
    assert db.user_doc.set_calls == []
    assert db.seen_uids == [DEFAULT_UID]


def test_register_existing_profile_returns_409_and_is_not_overwritten(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, db = auth_client(exists=True)

    response = client.post("/api/auth/register", headers=AUTH_HEADERS)

    assert response.status_code == 409
    assert response.json() == {"detail": "User profile already exists"}
    assert db.user_doc.create_calls == [{"created_at": SERVER_TIMESTAMP, "credits": 0}]
    assert db.user_doc.set_calls == []
    assert db.user_doc.update_calls == []


def test_register_uses_uid_from_token_not_from_request(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["uid"] = "second-user"
    client, db = auth_client(exists=False)

    response = client.post(
        "/api/auth/register?uid=someone-else",
        json={"uid": "someone-else"},
        headers={"Authorization": "Bearer second-token"},
    )

    assert response.status_code == 201
    assert response.json()["uid"] == "second-user"
    assert db.seen_uids == ["second-user"]


def test_register_accepts_unverified_email(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["email_verified"] = False
    client, _db = auth_client(exists=False)

    response = client.post("/api/auth/register", headers=AUTH_HEADERS)

    assert response.status_code == 201


@pytest.mark.parametrize("uid", UNSAFE_UIDS)
def test_register_rejects_unsafe_document_uid(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    uid: str,
) -> None:
    verify_token.return_value["uid"] = uid
    client, db = auth_client(exists=False)

    response = client.post("/api/auth/register", headers=AUTH_HEADERS)

    assert response.status_code == 401
    assert db.seen_uids == []


def test_register_firestore_failure_is_generic(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = auth_client(
        exists=False,
        create_error=FirestorePermissionDenied("private project configuration"),
    )
    response = client.post("/api/auth/register", headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}


def test_me_uses_new_users_own_document(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["uid"] = "second-user"
    client, db = auth_client()

    response = client.get("/api/auth/me", headers={"Authorization": "Bearer second-token"})

    assert response.status_code == 200
    assert response.json()["uid"] == "second-user"
    assert db.seen_uids == ["second-user"]


def test_me_rejects_unverified_user_before_reading_firestore(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
) -> None:
    verify_token.return_value["email_verified"] = False
    client, db = auth_client()

    response = client.get("/api/auth/me", headers=AUTH_HEADERS)

    assert response.status_code == 403
    assert db.seen_uids == []


@pytest.mark.parametrize("uid", UNSAFE_UIDS)
def test_me_rejects_unsafe_document_uid(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    verify_token: Mock,
    uid: str,
) -> None:
    verify_token.return_value["uid"] = uid
    client, db = auth_client()

    response = client.get("/api/auth/me", headers=AUTH_HEADERS)

    assert response.status_code == 401
    assert db.seen_uids == []


def test_me_firestore_failure_is_generic(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
) -> None:
    client, _db = auth_client(
        get_error=FirestorePermissionDenied("private project configuration")
    )

    response = client.get("/api/auth/me", headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}


def test_me_uninitialized_firebase_returns_503(
    auth_client: Callable[..., tuple[TestClient, FakeFirestoreDB]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: False)
    client, db = auth_client()

    response = client.get("/api/auth/me", headers=AUTH_HEADERS)

    assert response.status_code == 503
    assert db.seen_uids == []


def test_me_openapi_declares_bearer_authentication(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
