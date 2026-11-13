from fastapi import status


class AppError(Exception):
    """Base domain exception, mapped to an HTTP response by a global handler."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"
    headers: dict[str, str] | None = None

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class FirebaseNotInitializedError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Firebase is not initialized"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication required or credentials invalid"
    headers = {"WWW-Authenticate": "Bearer"}


class AuthenticationUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Authentication service unavailable"


class EmailNotVerifiedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Email verification required"


class ProfileUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "User profile service unavailable"
