from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.configs.games.ruleta import RuletaSettings, get_ruleta_settings
from src.configs.settings import Settings, get_settings
from src.models.auth import AuthenticatedUser
from src.services.auth_service import AuthService
from src.services.llm.evaluation_service import EvaluationService
from src.services.health_service import HealthService
from src.services.firebase_service import get_firestore
from src.services.flashcard_service import FlashcardService
from src.services.games.ruleta_service import RuletaService
from src.services.user_service import UserService
from src.utils.exceptions import AuthenticationError, EmailNotVerifiedError

bearer = HTTPBearer(auto_error=False)


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    return HealthService(settings)


def get_auth_service() -> AuthService:
    return AuthService()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    service: AuthService = Depends(get_auth_service),
) -> AuthenticatedUser:
    if credentials is None:
        raise AuthenticationError()
    # A sync dependency runs the blocking Admin SDK call in FastAPI's thread pool.
    return service.verify_token(credentials.credentials)


def get_verified_user(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.email_verified:
        raise EmailNotVerifiedError()
    return user


def get_user_service() -> UserService:
    return UserService(get_firestore())


def get_evaluation_service(request: Request) -> EvaluationService:
    return request.app.state.evaluation_service


def get_flashcard_service(settings: Settings = Depends(get_settings)) -> FlashcardService:
    return FlashcardService(settings.questions_path)


def get_ruleta_service(
    user_service: UserService = Depends(get_user_service),
    settings: RuletaSettings = Depends(get_ruleta_settings),
) -> RuletaService:
    return RuletaService(user_service=user_service, settings=settings)
