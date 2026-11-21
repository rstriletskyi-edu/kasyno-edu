from fastapi import APIRouter, Body, Depends

from src.dependencies import get_flashcard_service
from src.models.flashcard import FlashcardResponse, RandomFlashcardRequest
from src.services.flashcard_service import FlashcardService

router = APIRouter(prefix="/flashcards", tags=["flashcards"])

@router.post("/random", response_model=FlashcardResponse)
def get_random_flashcard(
    payload: RandomFlashcardRequest = Body(default_factory=RandomFlashcardRequest),
    service: FlashcardService = Depends(get_flashcard_service),
) -> FlashcardResponse:
    return service.get_random_flashcard(payload.excluded_ids)

@router.get("/{flashcard_id}", response_model=FlashcardResponse)
def get_concrete_flashcard(
    flashcard_id: str,
    service: FlashcardService = Depends(get_flashcard_service),
) -> FlashcardResponse:
    return service.get_flashcard_by_id(flashcard_id)
