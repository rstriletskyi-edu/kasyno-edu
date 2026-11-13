from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from pydantic import ValidationError

from src.models.auth import AuthenticatedUser
from src.services.firebase_service import is_firebase_initialized
from src.utils.exceptions import AuthenticationError, AuthenticationUnavailableError


class AuthService:
    def verify_token(self, token: str) -> AuthenticatedUser:
        if not is_firebase_initialized():
            raise AuthenticationUnavailableError()

        try:
            claims = auth.verify_id_token(token, check_revoked=True)
        except (auth.InvalidIdTokenError, auth.UserDisabledError, auth.UserNotFoundError):
            # Expired and revoked tokens also inherit from InvalidIdTokenError.
            raise AuthenticationError() from None
        except (FirebaseError, ValueError):
            # SDK configuration, certificate fetching and Auth service failures
            # must not be reported as incorrect user credentials.
            raise AuthenticationUnavailableError() from None

        try:
            return AuthenticatedUser.model_validate(claims)
        except ValidationError:
            raise AuthenticationError() from None
