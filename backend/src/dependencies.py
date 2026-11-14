from fastapi import Depends

from src.configs.settings import Settings, get_settings
from src.services.flashcard_service import FlashcardService
from src.services.health_service import HealthService


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    return HealthService(settings)


def get_flashcard_service() -> FlashcardService:
    return FlashcardService()
