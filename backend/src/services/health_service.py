from src.configs.settings import Settings
from src.models.health import HealthResponse
from src.services.firebase_service import is_firebase_initialized


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            app_name=self._settings.app_name,
            environment=self._settings.environment,
            firebase_initialized=is_firebase_initialized(),
        )
