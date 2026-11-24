from src.models.auth import AuthenticatedUser

DEFAULT_UID = "firebase-user-123"
AUTH_HEADERS = {"Authorization": "Bearer test-token"}
INVALID_AUTH_HEADERS: list[str | None] = [None, "", "Basic abc", "Bearer", "Bearer "]
UNSAFE_UIDS = ["x/private/y", ".", ".."]


def make_token_claims(uid: str = DEFAULT_UID, **overrides: object) -> dict[str, object]:
    claims: dict[str, object] = {
        "uid": uid,
        "email": "learner@example.test",
        "email_verified": True,
        "name": "Learner",
        "exp": 9999999999,
        "firebase": {"sign_in_provider": "password"},
    }
    claims.update(overrides)
    return claims


def make_user(
    uid: str = DEFAULT_UID,
    email: str | None = "learner@example.test",
    email_verified: bool = True,
    display_name: str | None = "Learner",
) -> AuthenticatedUser:
    return AuthenticatedUser(
        uid=uid,
        email=email,
        email_verified=email_verified,
        display_name=display_name,
    )
