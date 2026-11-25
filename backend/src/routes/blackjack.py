from fastapi import APIRouter, Depends, Response, status

from src.dependencies import get_blackjack_service, get_verified_user
from src.models.auth import AuthenticatedUser
from src.models.blackjack import BlackjackGameResponse, BlackjackStartRequest
from src.services.games.blackjack_service import BlackjackService

router = APIRouter(prefix="/games/blackjack", tags=["games", "blackjack"])

_ACTION_RESPONSES = {
    401: {"description": "Missing or invalid Firebase ID token"},
    403: {"description": "Email verification required"},
    404: {"description": "Blackjack game not found"},
    409: {"description": "Action is not allowed in the current game state"},
    503: {"description": "User profile or Firestore service unavailable"},
}


@router.post(
    "/start",
    response_model=BlackjackGameResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a Classic Blackjack round",
    responses={
        400: {"description": "Insufficient credits"},
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        409: {"description": "An active Blackjack game already exists"},
        422: {"description": "Invalid bet payload or table limits exceeded"},
        503: {"description": "User profile or Firestore service unavailable"},
    },
)
async def start_blackjack(
    payload: BlackjackStartRequest,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: BlackjackService = Depends(get_blackjack_service),
) -> BlackjackGameResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.start(user, payload)


@router.get(
    "/{game_id}",
    response_model=BlackjackGameResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the current state of a Classic Blackjack round",
    responses={
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        404: {"description": "Blackjack game not found"},
    },
)
async def get_blackjack_game(
    game_id: str,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: BlackjackService = Depends(get_blackjack_service),
) -> BlackjackGameResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.get_game(user, game_id)


@router.post(
    "/{game_id}/hit",
    response_model=BlackjackGameResponse,
    status_code=status.HTTP_200_OK,
    summary="Draw another card in Classic Blackjack",
    responses=_ACTION_RESPONSES,
)
async def hit_blackjack(
    game_id: str,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: BlackjackService = Depends(get_blackjack_service),
) -> BlackjackGameResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.hit(user, game_id)


@router.post(
    "/{game_id}/stand",
    response_model=BlackjackGameResponse,
    status_code=status.HTTP_200_OK,
    summary="Stand and resolve dealer turn in Classic Blackjack",
    responses=_ACTION_RESPONSES,
)
async def stand_blackjack(
    game_id: str,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: BlackjackService = Depends(get_blackjack_service),
) -> BlackjackGameResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.stand(user, game_id)


@router.post(
    "/{game_id}/double",
    response_model=BlackjackGameResponse,
    status_code=status.HTTP_200_OK,
    summary="Double down on an initial two-card Blackjack hand",
    responses={
        400: {"description": "Insufficient credits"},
        **_ACTION_RESPONSES,
    },
)
async def double_blackjack(
    game_id: str,
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: BlackjackService = Depends(get_blackjack_service),
) -> BlackjackGameResponse:
    response.headers["Cache-Control"] = "no-store"
    return await service.double_down(user, game_id)
