from fastapi import status


class AppError(Exception):
    """Base domain exception, mapped to an HTTP response by a global handler."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class FirebaseNotInitializedError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Firebase is not initialized"
