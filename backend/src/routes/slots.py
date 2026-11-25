from fastapi import APIRouter, Depends, Response, status

from src.configs.games.slots import SlotsSettings, get_slots_settings
from src.dependencies import get_slots_service, get_verified_user
from src.models.auth import AuthenticatedUser
from src.models.slots import SlotsConfigResponse, SlotsSpinRequest, SlotsSpinResponse
from src.services.games.slots_service import SlotsService

router = APIRouter(prefix="/games/slots", tags=["games", "slots"])


@router.get(
    "/config",
    response_model=SlotsConfigResponse,
    summary="Get classic 3x1 slot machine configuration and paytable",
)
async def get_slots_config(
    settings: SlotsSettings = Depends(get_slots_settings),
) -> SlotsConfigResponse:
    return SlotsService.build_config(settings)


@router.post(
    "/spin",
    response_model=SlotsSpinResponse,
    status_code=status.HTTP_200_OK,
    summary="Spin the classic 3x1 slot machine and settle wager",
    responses={
        400: {"description": "Insufficient credits"},
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        422: {"description": "Invalid bet payload or table limits exceeded"},
        503: {"description": "User profile or Firestore service unavailable"},
    },
)
async def spin_slots(
    payload: SlotsSpinRequest,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: SlotsService = Depends(get_slots_service),
) -> SlotsSpinResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.spin(user, payload)
