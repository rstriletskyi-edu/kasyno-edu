from fastapi import APIRouter, Depends, Query

from src.dependencies import get_flashcard_service
from src.models.flashcard import FlashcardResponse
from src.services.flashcard_service import FlashcardService

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


@router.get("/random", response_model=FlashcardResponse)
def get_random_flashcard(
    excluded_ids: list[str] = Query(default=[]),
    service: FlashcardService = Depends(get_flashcard_service),
) -> FlashcardResponse:
    return service.get_random_flashcard(excluded_ids)
