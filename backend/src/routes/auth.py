from fastapi import APIRouter, Depends, Response

from src.dependencies import get_user_service, get_verified_user
from src.models.auth import AuthenticatedUser, CurrentUserResponse
from src.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the verified current user and Firestore profile",
    description="On first access, provisions users/{verified UID} without overwriting existing data.",
    responses={
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        503: {"description": "Firebase Authentication or Firestore unavailable"},
    },
)
def get_me(
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: UserService = Depends(get_user_service),
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get_current_user(user)
