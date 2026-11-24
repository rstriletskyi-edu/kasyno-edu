from collections.abc import Callable

from fastapi.testclient import TestClient


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_rate_limiter_blocks_excessive_requests(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(rate_limit_max=5, rate_limit_window=60)

    for _ in range(5):
        res = client.get("/api/auth/me")
        assert res.status_code in (401, 200)

    blocked_res = client.get("/api/auth/me")
    assert blocked_res.status_code == 429
    assert blocked_res.json() == {"detail": "Too many requests. Please try again later."}
    assert "Retry-After" in blocked_res.headers


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"
