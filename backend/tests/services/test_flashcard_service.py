import pytest

from src.services.flashcard_service import FlashcardService
from src.utils.exceptions import NoFlashcardsAvailableError
from tests.fakes.realtime_db import FakeRealtimeRef


def _patch_db(monkeypatch: pytest.MonkeyPatch, questions_data: object) -> None:
    root = FakeRealtimeRef({"questions": questions_data})
    monkeypatch.setattr("src.services.flashcard_service.get_realtime_db", lambda: root)


def test_get_flashcard_ids_filters_unsafe_keys_and_non_dicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_db(
        monkeypatch,
        {
            "card-1": {"content": "Q1", "answer": "A1"},
            "card-2": {"content": "Q2", "answer": "A2"},
            "bad.key": {"content": "Q3", "answer": "A3"},
            "bad$key": {"content": "Q4", "answer": "A4"},
            "not-a-dict": "invalid",
        },
    )

    assert FlashcardService("questions").get_flashcard_ids() == ["card-1", "card-2"]


def test_get_flashcard_ids_returns_empty_when_snapshot_is_not_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_db(monkeypatch, None)
    assert FlashcardService("questions").get_flashcard_ids() == []

    _patch_db(monkeypatch, ["unexpected-list"])
    assert FlashcardService("questions").get_flashcard_ids() == []


def test_get_flashcard_by_id_returns_model_with_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_db(
        monkeypatch,
        {
            "card-1": {
                "id": "custom-id",
                "content": "Ile wynosi 2+2?",
                "answer": "4",
                "category": "Matematyka",
            },
            "card-2": {
                "id": "   ",
                "content": "Stolica Polski?",
                "answer": "Warszawa",
                "category": "",
            },
        },
    )
    service = FlashcardService("questions")

    first = service.get_flashcard_by_id("card-1")
    assert first.id == "custom-id"
    assert first.question == "Ile wynosi 2+2?"
    assert first.expected_answer == "4"
    assert first.category == "Matematyka"

    second = service.get_flashcard_by_id("card-2")
    assert second.id == "card-2"
    assert second.category == "Ogólne"


@pytest.mark.parametrize(
    "bad_id",
    ["", "missing", "bad.id", "bad$id", "bad#id", "bad[id]", "a/b"],
)
def test_get_flashcard_by_id_rejects_missing_and_unsafe_keys(
    monkeypatch: pytest.MonkeyPatch,
    bad_id: str,
) -> None:
    _patch_db(monkeypatch, {"card-1": {"content": "Q", "answer": "A"}})

    with pytest.raises(NoFlashcardsAvailableError):
        FlashcardService("questions").get_flashcard_by_id(bad_id)


@pytest.mark.parametrize(
    "record",
    [
        "not-a-dict",
        {},
        {"content": "   ", "answer": "A"},
        {"content": "Q", "answer": "   "},
        {"content": 123, "answer": "A"},
    ],
)
def test_get_flashcard_by_id_rejects_malformed_records(
    monkeypatch: pytest.MonkeyPatch,
    record: object,
) -> None:
    _patch_db(monkeypatch, {"card-1": record})

    with pytest.raises(NoFlashcardsAvailableError):
        FlashcardService("questions").get_flashcard_by_id("card-1")


def test_get_random_flashcard_excludes_ids_and_handles_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_db(
        monkeypatch,
        {
            "card-1": {"content": "Q1", "answer": "A1"},
            "card-2": {"content": "Q2", "answer": "A2"},
        },
    )
    service = FlashcardService("questions")

    picked = service.get_random_flashcard(["card-1"])
    assert picked.id == "card-2"
    assert picked.question == "Q2"

    with pytest.raises(NoFlashcardsAvailableError):
        service.get_random_flashcard(["card-1", "card-2"])
