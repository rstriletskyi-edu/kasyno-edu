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


class NoFlashcardsAvailableError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "No available flashcards"


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


class ProfileAlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "User profile already exists"


class LlmNotConfiguredError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "LLM is not configured"


class LlmSessionNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "LLM session not found"


class LlmRateLimitExceededError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Too many LLM requests. Please try again later."

    def __init__(self, retry_after_seconds: int, detail: str | None = None) -> None:
        self.headers = {"Retry-After": str(max(1, retry_after_seconds))}
        super().__init__(detail)


class AnswerTooLongError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "User answer exceeds the maximum length"


class LlmTimeoutError(AppError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    detail = "LLM evaluation timed out"


class FlashcardLookupTimeoutError(AppError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    detail = "Flashcard lookup timed out"


class LlmEvaluationError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "LLM evaluation failed"


class InsufficientCreditsError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Insufficient credits"


class BetLimitExceededError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Bet exceeds configured table limits"
