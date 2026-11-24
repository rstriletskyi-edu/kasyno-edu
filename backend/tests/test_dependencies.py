from collections.abc import Callable
from unittest.mock import Mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from firebase_admin import auth
from firebase_admin.exceptions import PermissionDeniedError, UnavailableError
import pytest

from src.dependencies import get_current_user, get_verified_user
from src.models.auth import AuthenticatedUser
from tests.fakes.auth import AUTH_HEADERS, DEFAULT_UID, INVALID_AUTH_HEADERS


@pytest.fixture
def dep_client(
    make_client: Callable[..., TestClient],
    verify_token: Mock,
) -> TestClient:
    def add_test_routes(app: FastAPI) -> None:
        @app.get("/test/identity")
        def identity(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
            return user

        @app.get("/test/verified")
        def verified(user: AuthenticatedUser = Depends(get_verified_user)) -> AuthenticatedUser:
            return user

    return make_client(configure_app=add_test_routes)


@pytest.mark.parametrize("authorization", INVALID_AUTH_HEADERS)
@pytest.mark.parametrize("path", ["/test/identity", "/api/auth/me"])
def test_missing_or_wrong_auth_scheme_returns_401(
    dep_client: TestClient,
    verify_token: Mock,
    authorization: str | None,
    path: str,
) -> None:
    headers = {"Authorization": authorization} if authorization is not None else {}
    response = dep_client.get(path, headers=headers)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    verify_token.assert_not_called()


def test_valid_token_returns_only_verified_identity(
    dep_client: TestClient,
    verify_token: Mock,
) -> None:
    response = dep_client.get(
        "/test/identity?uid=another-user",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "uid": DEFAULT_UID,
        "email": "learner@example.test",
        "email_verified": True,
        "display_name": "Learner",
    }
    verify_token.assert_called_once_with("test-token", check_revoked=True)


@pytest.mark.parametrize(
    "error",
    [
        auth.InvalidIdTokenError("malformed token: sensitive-detail"),
        auth.InvalidIdTokenError("wrong audience/project: sensitive-detail"),
        auth.InvalidIdTokenError("invalid signature: sensitive-detail"),
        auth.ExpiredIdTokenError("expired token: sensitive-detail", cause=None),
        auth.RevokedIdTokenError("revoked token: sensitive-detail"),
        auth.UserDisabledError("disabled account: sensitive-detail"),
        auth.UserNotFoundError("deleted account: sensitive-detail"),
    ],
)
@pytest.mark.parametrize("path", ["/test/identity", "/api/auth/me"])
def test_invalid_identity_returns_generic_401(
    dep_client: TestClient,
    verify_token: Mock,
    error: Exception,
    caplog: pytest.LogCaptureFixture,
    path: str,
) -> None:
    verify_token.side_effect = error
    response = dep_client.get(path, headers={"Authorization": "Bearer secret-test-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required or credentials invalid"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert "secret-test-token" not in response.text + caplog.text
    assert "sensitive-detail" not in response.text + caplog.text


@pytest.mark.parametrize(
    "error",
    [
        auth.CertificateFetchError("certificate service: sensitive-detail", cause=None),
        UnavailableError("network failure: sensitive-detail"),
        PermissionDeniedError("service account permission: sensitive-detail"),
        ValueError("SDK configuration: sensitive-detail"),
    ],
)
def test_auth_infrastructure_errors_return_generic_503(
    dep_client: TestClient,
    verify_token: Mock,
    error: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    verify_token.side_effect = error
    response = dep_client.get(
        "/test/identity", headers={"Authorization": "Bearer secret-test-token"}
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication service unavailable"}
    assert "www-authenticate" not in response.headers
    assert "secret-test-token" not in response.text + caplog.text
    assert "sensitive-detail" not in response.text + caplog.text


def test_uninitialized_firebase_fails_closed(
    dep_client: TestClient,
    verify_token: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: False)
    response = dep_client.get("/test/identity", headers=AUTH_HEADERS)

    assert response.status_code == 503
    verify_token.assert_not_called()


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"uid": ""},
        {"uid": 123},
        {"uid": "x" * 129},
        {"uid": "user", "email_verified": "true"},
    ],
)
def test_unusable_verified_claims_are_rejected(
    dep_client: TestClient,
    verify_token: Mock,
    claims: dict[str, object],
) -> None:
    verify_token.return_value = claims
    response = dep_client.get("/test/identity", headers=AUTH_HEADERS)

    assert response.status_code == 401


def test_optional_profile_fields_can_be_absent(
    dep_client: TestClient,
    verify_token: Mock,
) -> None:
    verify_token.return_value = {"uid": "provider-user"}
    response = dep_client.get("/test/identity", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "uid": "provider-user",
        "email": None,
        "email_verified": False,
        "display_name": None,
    }


def test_unverified_user_is_authenticated_but_cannot_access_verified_route(
    dep_client: TestClient,
    verify_token: Mock,
) -> None:
    verify_token.return_value["email_verified"] = False

    assert dep_client.get("/test/identity", headers=AUTH_HEADERS).status_code == 200
    response = dep_client.get("/test/verified", headers=AUTH_HEADERS)

    assert response.status_code == 403
    assert response.json() == {"detail": "Email verification required"}


def test_verified_user_can_access_verified_route(dep_client: TestClient) -> None:
    response = dep_client.get("/test/verified", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["uid"] == DEFAULT_UID
