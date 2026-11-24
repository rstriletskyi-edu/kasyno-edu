from unittest.mock import Mock

from firebase_admin import auth
from firebase_admin.exceptions import PermissionDeniedError, UnavailableError
import pytest

from src.services.auth_service import AuthService
from src.utils.exceptions import AuthenticationError, AuthenticationUnavailableError
from tests.fakes.auth import DEFAULT_UID


def test_verify_token_returns_authenticated_user(verify_token: Mock) -> None:
    user = AuthService().verify_token("valid-token")

    assert user.uid == DEFAULT_UID
    assert user.email == "learner@example.test"
    assert user.email_verified is True
    assert user.display_name == "Learner"
    verify_token.assert_called_once_with("valid-token", check_revoked=True)


def test_verify_token_allows_absent_optional_fields(verify_token: Mock) -> None:
    verify_token.return_value = {"uid": "provider-user"}

    user = AuthService().verify_token("valid-token")

    assert user.uid == "provider-user"
    assert user.email is None
    assert user.email_verified is False
    assert user.display_name is None


def test_verify_token_raises_unavailable_when_firebase_uninitialized(
    verify_token: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.auth_service.is_firebase_initialized", lambda: False)

    with pytest.raises(AuthenticationUnavailableError):
        AuthService().verify_token("any-token")

    verify_token.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        auth.InvalidIdTokenError("malformed"),
        auth.ExpiredIdTokenError("expired", cause=None),
        auth.RevokedIdTokenError("revoked"),
        auth.UserDisabledError("disabled"),
        auth.UserNotFoundError("deleted"),
    ],
)
def test_verify_token_maps_invalid_token_errors(
    verify_token: Mock,
    error: Exception,
) -> None:
    verify_token.side_effect = error

    with pytest.raises(AuthenticationError):
        AuthService().verify_token("bad-token")


@pytest.mark.parametrize(
    "error",
    [
        auth.CertificateFetchError("cert error", cause=None),
        UnavailableError("unavailable"),
        PermissionDeniedError("denied"),
        ValueError("misconfigured"),
    ],
)
def test_verify_token_maps_infrastructure_errors(
    verify_token: Mock,
    error: Exception,
) -> None:
    verify_token.side_effect = error

    with pytest.raises(AuthenticationUnavailableError):
        AuthService().verify_token("token")


@pytest.mark.parametrize(
    "claims",
    [{}, {"uid": ""}, {"uid": 123}, {"uid": "x" * 129}, {"uid": "user", "email_verified": "true"}],
)
def test_verify_token_rejects_invalid_claims(
    verify_token: Mock,
    claims: dict[str, object],
) -> None:
    verify_token.return_value = claims

    with pytest.raises(AuthenticationError):
        AuthService().verify_token("token")
