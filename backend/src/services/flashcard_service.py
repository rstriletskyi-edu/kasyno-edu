import random

from firebase_admin.db import Reference

from src.models.flashcard import FlashcardResponse
from src.services.firebase_service import get_realtime_db
from src.utils.exceptions import NoFlashcardsAvailableError

_INVALID_KEY_CHARS = ".$#[]/"


class FlashcardService:
    def __init__(self, questions_path: str) -> None:
        self._questions_path = questions_path

    def get_flashcard_ids(self) -> list[str]:
        snapshot = self._questions().get()
        if not isinstance(snapshot, dict):
            return []
        return [
            key
            for key, value in snapshot.items()
            if isinstance(key, str) and isinstance(value, dict) and _is_safe_key(key)
        ]

    def get_flashcard_by_id(self, flashcard_id: str) -> FlashcardResponse:
        if not _is_safe_key(flashcard_id):
            raise NoFlashcardsAvailableError()

        data = self._questions().child(flashcard_id).get()
        if not isinstance(data, dict):
            raise NoFlashcardsAvailableError()

        return _to_flashcard(flashcard_id, data)

    def get_random_flashcard(self, excluded_ids: list[str]) -> FlashcardResponse:
        excluded = set(excluded_ids)
        available_ids = [
            flashcard_id
            for flashcard_id in self.get_flashcard_ids()
            if flashcard_id not in excluded
        ]
        if not available_ids:
            raise NoFlashcardsAvailableError()

        return self.get_flashcard_by_id(random.choice(available_ids))

    def _questions(self) -> Reference:
        return get_realtime_db().child(self._questions_path)


def _is_safe_key(key: str) -> bool:
    return bool(key) and not any(char in key for char in _INVALID_KEY_CHARS)


def _to_flashcard(key: str, data: dict[str, object]) -> FlashcardResponse:
    content = data.get("content")
    answer = data.get("answer")
    if not isinstance(content, str) or not content.strip():
        raise NoFlashcardsAvailableError()
    if not isinstance(answer, str) or not answer.strip():
        raise NoFlashcardsAvailableError()

    record_id = data.get("id")
    category = data.get("category")
    return FlashcardResponse(
        id=record_id if isinstance(record_id, str) and record_id.strip() else key,
        question=content,
        expected_answer=answer,
        category=category if isinstance(category, str) and category.strip() else "Ogólne",
    )
