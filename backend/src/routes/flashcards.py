from fastapi import APIRouter, Depends

from src.dependencies import get_flashcard_service
from src.models.flashcard import FlashcardsResponse
from src.services.flashcard_service import FlashcardService

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get("", response_model=FlashcardsResponse)
def get_flashcards(service: FlashcardService = Depends(get_flashcard_service)) -> FlashcardsResponse:
    return service.get_flashcards()