from src.models.flashcard import FlashcardResponse, FlashcardsResponse
from src.services.firebase_service import get_firestore


class FlashcardService:
    def get_flashcards(self) -> FlashcardsResponse:
        documents = get_firestore().collection("flashcards").stream()

        items = [
            FlashcardResponse(
                id=document.id,
                question=data["question"],
                expected_answer=data["expected_answer"],
                category=data.get("category", "Ogólne"),
            )
            for document in documents
            if (data := document.to_dict())
        ]

        items.sort(key=lambda item: item.id)
        return FlashcardsResponse(items=items)
