from fastapi import APIRouter, Depends, status

from src.dependencies import get_health_service
from src.models.health import HealthResponse
from src.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def get_health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return await service.get_health()
