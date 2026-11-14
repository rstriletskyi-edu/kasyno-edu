from src.models.flashcard import FlashcardResponse, FlashcardsResponse
from src.services.firebase_service import get_firestore


class FlashcardService:
    def get_flashcards(self) -> FlashcardsResponse:
        documents = get_firestore().collection("flashcards").stream()
        items = [
            FlashcardResponse(
                id=document.id,
                question=document.to_dict()["question"],
                expected_answer=document.to_dict()["expected_answer"],
                category=document.to_dict().get("category", "Ogólne"),
            )
            for document in documents
        ]
        items.sort(key=lambda flashcard: flashcard.id)
        return FlashcardsResponse(items=items)