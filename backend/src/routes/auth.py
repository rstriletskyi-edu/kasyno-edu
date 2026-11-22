from fastapi import APIRouter, Depends, Response, status

from src.dependencies import get_current_user, get_user_service, get_verified_user
from src.models.auth import AuthenticatedUser, CurrentUserResponse
from src.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get the verified current user and Firestore profile",
    description="Read-only. Returns 503 if users/{verified UID} does not exist; use POST /auth/register.",
    responses={
        401: {"description": "Missing or invalid Firebase ID token"},
        403: {"description": "Email verification required"},
        503: {"description": "Profile missing, or Firebase Authentication or Firestore unavailable"},
    },
)
def get_me(
    response: Response,
    user: AuthenticatedUser = Depends(get_verified_user),
    service: UserService = Depends(get_user_service),
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    return service.get_current_user(user)


@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the initial Firestore profile for the authenticated user",
    description=(
        "Creates users/{uid} (created_at, credits=0) only if it does not exist; an existing "
        "profile is never overwritten. The UID comes from the Firebase ID token. "
        "Returns 201 when created, 200 when the profile already existed."
    ),
    responses={
        200: {"description": "Profile already existed"},
        401: {"description": "Missing or invalid Firebase ID token"},
        503: {"description": "Firebase Authentication or Firestore unavailable"},
    },
)
def register(
    response: Response,
    user: AuthenticatedUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    profile, created = service.register_user(user)
    if not created:
        response.status_code = status.HTTP_200_OK
    return profile
