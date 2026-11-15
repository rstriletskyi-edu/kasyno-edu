from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.main import create_app
from src.middlewares.security import RateLimiterMiddleware
from src.models.auth import AuthenticatedUser


def test_security_headers_are_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_rate_limiter_blocks_excessive_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.main.init_firebase", lambda settings: False)
    # Create test app configured with low threshold (5 requests)
    app = create_app(rate_limit_max=5, rate_limit_window=60)

    with TestClient(app) as client:
        # 5 allowed requests
        for _ in range(5):
            res = client.get("/api/auth/me")
            assert res.status_code in (401, 200)

        # 6th request must trigger rate limit
        blocked_res = client.get("/api/auth/me")
        assert blocked_res.status_code == 429
        assert blocked_res.json() == {"detail": "Too many requests. Please try again later."}
        assert "Retry-After" in blocked_res.headers


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
