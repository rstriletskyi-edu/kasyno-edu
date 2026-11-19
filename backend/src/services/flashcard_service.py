import random

from src.models.flashcard import FlashcardResponse
from src.services.firebase_service import get_firestore
from src.utils.exceptions import NoFlashcardsAvailableError


class FlashcardService:
    def get_flashcard_ids(self) -> list[str]:
        return [document.id for document in get_firestore().collection("flashcards").stream()]

    def get_flashcard_by_id(self, flashcard_id: str) -> FlashcardResponse:
        document = get_firestore().collection("flashcards").document(flashcard_id).get()
        if not document.exists:
            raise NoFlashcardsAvailableError()

        data = document.to_dict()
        return FlashcardResponse(
            id=document.id,
            question=data["question"],
            expected_answer=data["expected_answer"],
            category=data.get("category", "Ogólne"),
        )

    def get_random_flashcard(self, excluded_ids: list[str]) -> FlashcardResponse:
        available_ids = [
            flashcard_id
            for flashcard_id in self.get_flashcard_ids()
            if flashcard_id not in excluded_ids
        ]
        if not available_ids:
            raise NoFlashcardsAvailableError()

        return self.get_flashcard_by_id(random.choice(available_ids))
