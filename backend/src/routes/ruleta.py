from fastapi import APIRouter, Depends, Response, status

from src.dependencies import get_ruleta_service, get_verified_user
from src.models.auth import AuthenticatedUser
from src.models.ruleta import RuletaSpinRequest, RuletaSpinResponse
from src.services.games.ruleta_service import RuletaService

router = APIRouter(prefix="/games/ruleta", tags=["games", "ruleta"])


@router.post(
    "/spin",
    response_model=RuletaSpinResponse,
    status_code=status.HTTP_200_OK,
    summary="Spin the European Roulette wheel and settle bets",
    responses={
        400: {"description": "Insufficient credits"},
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        422: {"description": "Invalid bet payload or table limits exceeded"},
        503: {"description": "User profile or Firestore service unavailable"},
    },
)
async def spin_ruleta(
    payload: RuletaSpinRequest,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: RuletaService = Depends(get_ruleta_service),
) -> RuletaSpinResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.spin(user, payload)
