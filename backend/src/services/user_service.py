from google.api_core.exceptions import AlreadyExists, GoogleAPICallError, RetryError
from google.auth.exceptions import GoogleAuthError
from google.cloud.firestore import Client, SERVER_TIMESTAMP
from pydantic import ValidationError

from src.models.auth import AuthenticatedUser, CurrentUserResponse, UserProfile
from src.utils.exceptions import AuthenticationError, ProfileUnavailableError


class UserService:
    def __init__(self, db: Client) -> None:
        self._db = db

    def get_current_user(self, user: AuthenticatedUser) -> CurrentUserResponse:
        # Firebase custom UIDs can contain slashes, but a document ID cannot.
        # Never let a UID select a nested Firestore path.
        if "/" in user.uid or user.uid in {".", ".."}:
            raise AuthenticationError()

        try:
            reference = self._db.collection("users").document(user.uid)
            snapshot = reference.get()
            if not snapshot.exists:
                try:
                    reference.create({"created_at": SERVER_TIMESTAMP})
                except AlreadyExists:
                    # Another request provisioned this UID after our initial read.
                    pass
                snapshot = reference.get()
            if not snapshot.exists:
                raise ProfileUnavailableError()
            profile = UserProfile.model_validate(snapshot.to_dict())
        except (GoogleAPICallError, RetryError, GoogleAuthError, ValidationError):
            raise ProfileUnavailableError() from None

        return CurrentUserResponse(**user.model_dump(), profile=profile)
