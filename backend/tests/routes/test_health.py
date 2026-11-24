from unittest.mock import Mock

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_stays_public(client: TestClient, verify_token: Mock) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    verify_token.assert_not_called()
