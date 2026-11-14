from collections.abc import Iterator
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from firebase_admin import auth
from firebase_admin.exceptions import PermissionDeniedError, UnavailableError
from google.api_core.exceptions import AlreadyExists
from google.api_core.exceptions import PermissionDenied as FirestorePermissionDenied

from src.dependencies import get_current_user, get_verified_user
from src.main import create_app
from src.models.auth import AuthenticatedUser


@pytest.fixture
def verify_token(monkeypatch: pytest.MonkeyPatch) -> Mock:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: True)
    verify = Mock(return_value={
        "uid": "firebase-user-123",
        "email": "learner@example.test",
        "email_verified": True,
        "name": "Learner",
        "exp": 9999999999,
        "firebase": {"sign_in_provider": "password"},
    })
    monkeypatch.setattr("src.services.auth_service.auth.verify_id_token", verify)
    return verify


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, verify_token: Mock) -> Iterator[TestClient]:
    # No real service-account credentials or network calls, even if configured locally.
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    app = create_app()

    # Exercise the real dependency through test-only routes. Production /me comes next.
    @app.get("/test/identity")
    def identity(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        return user

    @app.get("/test/verified")
    def verified(user: AuthenticatedUser = Depends(get_verified_user)) -> AuthenticatedUser:
        return user

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("authorization", [None, "", "Basic abc", "Bearer", "Bearer "])
@pytest.mark.parametrize("path", ["/test/identity", "/api/auth/me"])
def test_missing_or_wrong_auth_scheme_returns_401(
    client: TestClient, verify_token: Mock, authorization: str | None, path: str
) -> None:
    headers = {"Authorization": authorization} if authorization is not None else {}
    response = client.get(path, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    verify_token.assert_not_called()


def test_valid_token_returns_only_verified_identity(client: TestClient, verify_token: Mock) -> None:
    response = client.get(
        "/test/identity?uid=another-user",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "uid": "firebase-user-123",
        "email": "learner@example.test",
        "email_verified": True,
        "display_name": "Learner",
    }
    verify_token.assert_called_once_with("test-token", check_revoked=True)


@pytest.mark.parametrize("error", [
    auth.InvalidIdTokenError("malformed token: sensitive-detail"),
    auth.InvalidIdTokenError("wrong audience/project: sensitive-detail"),
    auth.InvalidIdTokenError("invalid signature: sensitive-detail"),
    auth.ExpiredIdTokenError("expired token: sensitive-detail", cause=None),
    auth.RevokedIdTokenError("revoked token: sensitive-detail"),
    auth.UserDisabledError("disabled account: sensitive-detail"),
    auth.UserNotFoundError("deleted account: sensitive-detail"),
])
@pytest.mark.parametrize("path", ["/test/identity", "/api/auth/me"])
def test_invalid_identity_returns_generic_401(
    client: TestClient, verify_token: Mock, error: Exception, caplog: pytest.LogCaptureFixture,
    path: str,
) -> None:
    verify_token.side_effect = error
    response = client.get(path, headers={"Authorization": "Bearer secret-test-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required or credentials invalid"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert "secret-test-token" not in response.text + caplog.text
    assert "sensitive-detail" not in response.text + caplog.text


@pytest.mark.parametrize("error", [
    auth.CertificateFetchError("certificate service: sensitive-detail", cause=None),
    UnavailableError("network failure: sensitive-detail"),
    PermissionDeniedError("service account permission: sensitive-detail"),
    ValueError("SDK configuration: sensitive-detail"),
])
def test_auth_infrastructure_errors_return_generic_503(
    client: TestClient, verify_token: Mock, error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    verify_token.side_effect = error
    response = client.get("/test/identity", headers={"Authorization": "Bearer secret-test-token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    assert "www-authenticate" not in response.headers
    assert "secret-test-token" not in response.text + caplog.text
    assert "sensitive-detail" not in response.text + caplog.text


def test_uninitialized_firebase_fails_closed(
    client: TestClient, verify_token: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: False)
    response = client.get("/test/identity", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 503
    verify_token.assert_not_called()


@pytest.mark.parametrize("claims", [
    {},
    {"uid": ""},
    {"uid": 123},
    {"uid": "x" * 129},
    {"uid": "user", "email_verified": "true"},
])
def test_unusable_verified_claims_are_rejected(
    client: TestClient, verify_token: Mock, claims: dict
) -> None:
    verify_token.return_value = claims
    response = client.get("/test/identity", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 401


def test_optional_profile_fields_can_be_absent(client: TestClient, verify_token: Mock) -> None:
    verify_token.return_value = {"uid": "provider-user"}
    response = client.get("/test/identity", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == {
        "uid": "provider-user", "email": None, "email_verified": False, "display_name": None,
    }


def test_unverified_user_is_authenticated_but_cannot_access_verified_route(
    client: TestClient, verify_token: Mock
) -> None:
    verify_token.return_value["email_verified"] = False
    headers = {"Authorization": "Bearer test-token"}

    assert client.get("/test/identity", headers=headers).status_code == 200
    response = client.get("/test/verified", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}


def test_verified_user_can_access_verified_route(client: TestClient) -> None:
    response = client.get("/test/verified", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json()["uid"] == "firebase-user-123"


def test_health_stays_public(client: TestClient, verify_token: Mock) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    verify_token.assert_not_called()


@pytest.fixture
def profile_db(monkeypatch: pytest.MonkeyPatch) -> Mock:
    db = Mock()
    reference = db.collection.return_value.document.return_value
    snapshot = Mock(exists=True)
    snapshot.to_dict.return_value = {
        "created_at": datetime(2026, 11, 12, tzinfo=timezone.utc),
        "tokens": 999,
    }
    reference.get.return_value = snapshot
    monkeypatch.setattr("src.dependencies.get_firestore", lambda: db)
    return db


def test_me_reads_only_token_uid_and_does_not_overwrite_existing_profile(
    client: TestClient, profile_db: Mock
) -> None:
    response = client.get(
        "/api/auth/me?uid=someone-else", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "uid": "firebase-user-123", "email": "learner@example.test",
        "email_verified": True, "display_name": "Learner",
        "profile": {"created_at": "2026-11-12T00:00:00Z"},
    }
    profile_db.collection.assert_called_once_with("users")
    reference = profile_db.collection.return_value.document
    reference.assert_called_once_with("firebase-user-123")
    reference.return_value.create.assert_not_called()
    reference.return_value.set.assert_not_called()


@pytest.mark.parametrize("concurrent", [False, True])
def test_me_initializes_missing_profile_without_overwriting_concurrent_creation(
    client: TestClient, profile_db: Mock, concurrent: bool
) -> None:
    from google.cloud.firestore import SERVER_TIMESTAMP

    reference = profile_db.collection.return_value.document.return_value
    existing = reference.get.return_value
    reference.get.side_effect = [Mock(exists=False), existing]
    if concurrent:
        reference.create.side_effect = AlreadyExists("Concurrent profile creation")

    response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    reference.create.assert_called_once_with({"created_at": SERVER_TIMESTAMP})
    reference.set.assert_not_called()


def test_me_uses_new_users_own_document(
    client: TestClient, profile_db: Mock, verify_token: Mock
) -> None:
    verify_token.return_value["uid"] = "second-user"
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer second-token"})

    assert response.status_code == 200
    assert response.json()["uid"] == "second-user"
    profile_db.collection.return_value.document.assert_called_once_with("second-user")


def test_me_rejects_unverified_user_before_reading_firestore(
    client: TestClient, profile_db: Mock, verify_token: Mock
) -> None:
    verify_token.return_value["email_verified"] = False
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 403
    profile_db.collection.assert_not_called()


@pytest.mark.parametrize("uid", ["x/private/y", ".", ".."])
def test_me_rejects_unsafe_document_uid(
    client: TestClient, profile_db: Mock, verify_token: Mock, uid: str
) -> None:
    verify_token.return_value["uid"] = uid
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 401
    profile_db.collection.assert_not_called()


def test_me_firestore_failure_is_generic(client: TestClient, profile_db: Mock) -> None:
    profile_db.collection.return_value.document.return_value.get.side_effect = (
        FirestorePermissionDenied("private project configuration")
    )
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 503
    assert response.json() == {"detail": "User profile service unavailable"}


def test_me_uninitialized_firebase_returns_503(
    client: TestClient, profile_db: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: False)
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 503
    profile_db.collection.assert_not_called()


def test_me_openapi_declares_bearer_authentication(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    assert schema["paths"]["/api/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
