from pydantic import ValidationError
import pytest

from src.models.auth import AuthenticatedUser


def test_pydantic_rejects_invalid_uid_and_injection() -> None:
    # UID must be string between 1 and 128 characters
    with pytest.raises(ValidationError):
        AuthenticatedUser.model_validate({"uid": "", "email": "valid@test.com"})

    # Injection with non-string type or oversized payload
    with pytest.raises(ValidationError):
        AuthenticatedUser.model_validate({"uid": ["$ne", None], "email": "valid@test.com"})

    with pytest.raises(ValidationError):
        AuthenticatedUser.model_validate({"uid": "a" * 150, "email": "valid@test.com"})

    # Valid payload succeeds
    user = AuthenticatedUser.model_validate({"uid": "valid-uid-123", "email": "test@example.com"})
    assert user.uid == "valid-uid-123"
