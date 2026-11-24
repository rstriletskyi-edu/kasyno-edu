from collections.abc import Callable

from fastapi.testclient import TestClient
import pytest

from src.dependencies import get_flashcard_service
from src.services.flashcard_service import FlashcardService
from tests.fakes.realtime_db import FakeRealtimeRef


@pytest.fixture
def flashcard_client(
    make_client: Callable[..., TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[dict[str, object] | None], TestClient]:
    def _open(questions_data: dict[str, object] | None) -> TestClient:
        root = FakeRealtimeRef({"questions": questions_data})
        monkeypatch.setattr("src.services.flashcard_service.get_realtime_db", lambda: root)
        service = FlashcardService("questions")
        return make_client(dependency_overrides={get_flashcard_service: lambda: service})

    return _open


def test_get_random_flashcard_accepts_default_body_and_excluded_ids(
    flashcard_client: Callable[[dict[str, object] | None], TestClient],
) -> None:
    client = flashcard_client(
        {
            "card-1": {"content": "Q1", "answer": "A1", "category": "Historia"},
            "card-2": {"content": "Q2", "answer": "A2"},
        }
    )

    default_res = client.post("/api/flashcards/random")
    assert default_res.status_code == 200
    assert default_res.json()["id"] in {"card-1", "card-2"}

    filtered_res = client.post("/api/flashcards/random", json={"excluded_ids": ["card-1"]})
    assert filtered_res.status_code == 200
    assert filtered_res.json() == {
        "id": "card-2",
        "question": "Q2",
        "expected_answer": "A2",
        "category": "Ogólne",
    }


def test_get_random_flashcard_returns_404_when_exhausted_and_422_on_oversized_list(
    flashcard_client: Callable[[dict[str, object] | None], TestClient],
) -> None:
    client = flashcard_client({"card-1": {"content": "Q1", "answer": "A1"}})

    exhausted = client.post("/api/flashcards/random", json={"excluded_ids": ["card-1"]})
    assert exhausted.status_code == 404
    assert exhausted.json() == {"detail": "No available flashcards"}

    too_many = client.post(
        "/api/flashcards/random",
        json={"excluded_ids": [f"id-{i}" for i in range(5001)]},
    )
    assert too_many.status_code == 422


def test_get_concrete_flashcard_returns_card_or_404(
    flashcard_client: Callable[[dict[str, object] | None], TestClient],
) -> None:
    client = flashcard_client(
        {"card-1": {"content": "Q1", "answer": "A1", "category": "Geografia"}}
    )

    found = client.get("/api/flashcards/card-1")
    assert found.status_code == 200
    assert found.json() == {
        "id": "card-1",
        "question": "Q1",
        "expected_answer": "A1",
        "category": "Geografia",
    }

    assert client.get("/api/flashcards/missing").status_code == 404
    assert client.get("/api/flashcards/bad.key").status_code == 404
