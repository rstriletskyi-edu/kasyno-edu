import math
from numbers import Real

from google.cloud import firestore
from google.api_core.exceptions import AlreadyExists, GoogleAPICallError, RetryError
from google.auth.exceptions import GoogleAuthError
from google.cloud.firestore import Client, SERVER_TIMESTAMP
from pydantic import ValidationError

from src.models.auth import AuthenticatedUser, CurrentUserResponse, UserProfile
from src.utils.exceptions import (
    AuthenticationError,
    ProfileAlreadyExistsError,
    ProfileUnavailableError,
)


class UserService:
    def __init__(self, db: Client) -> None:
        self._db = db

    @staticmethod
    def _validate_positive_amount(value: float) -> float:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Credits value must be positive")
        amount = float(value)
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Credits value must be positive")
        return amount

    def _validate_uid(self, uid: str) -> None:
        if "/" in uid or uid in {".", ".."}:
            raise AuthenticationError()

    def _modify_credits(
        self,
        user: AuthenticatedUser,
        value: float,
        reason: str,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Credits value must not be zero")
        signed_amount = float(value)
        if not math.isfinite(signed_amount) or signed_amount == 0:
            raise ValueError("Credits value must not be zero")
        self._validate_uid(user.uid)

        user_reference = self._db.collection("users").document(user.uid)
        transaction_reference = (
            user_reference.collection("transactions").document()
        )

        @firestore.transactional
        def modify(transaction, reference, signed_amount):
            snapshot = transaction.get(reference)
            data = snapshot.to_dict() if snapshot.exists else {}
            current_credits = data.get("credits", 0)
            transaction.update(
                reference,
                {"credits": current_credits + signed_amount},
            )
            transaction.create(
                transaction_reference,
                {
                    "value": float(signed_amount),
                    "Reason": reason,
                    "timestamp": SERVER_TIMESTAMP,
                },
            )

        transaction = self._db.transaction()
        modify(transaction, user_reference, signed_amount)

    def add_credits(
        self,
        user: AuthenticatedUser,
        value: float,
        reason: str,
    ) -> None:
        amount = self._validate_positive_amount(value)
        self._modify_credits(user, amount, reason)

    def remove_credits(
        self,
        user: AuthenticatedUser,
        value: float,
        reason: str,
    ) -> None:
        amount = self._validate_positive_amount(value)
        self._modify_credits(user, -amount, reason)

    def get_credits(self, user: AuthenticatedUser) -> int:
        self._validate_uid(user.uid)
        snapshot = (
            self._db.collection("users")
            .document(user.uid)
            .get()
        )
        if not snapshot.exists:
            return 0
        data = snapshot.to_dict() or {}
        credits = data.get("credits", 0)
        return int(credits)

    def record_transaction(self, uid: str, value: float, reason: str) -> None:
        if "/" in uid or uid in {".", ".."}:
            raise AuthenticationError()

        reference = (
            self._db.collection("users")
            .document(uid)
            .collection("transactions")
            .document()
        )
        reference.create(
            {
                "value": float(value),
                "Reason": reason,
                "timestamp": SERVER_TIMESTAMP,
            }
        )

    def _validate_profile_uid(self, uid: str) -> None:
        # Firebase custom UIDs can contain slashes, but a document ID cannot.
        # Never let a UID select a nested Firestore path.
        if "/" in uid or uid in {".", ".."}:
            raise AuthenticationError()

    def get_current_user(self, user: AuthenticatedUser) -> CurrentUserResponse:
        """Read-only: never creates or modifies users/{uid}."""
        self._validate_profile_uid(user.uid)

        try:
            snapshot = self._db.collection("users").document(user.uid).get()
            if not snapshot.exists:
                raise ProfileUnavailableError()
            profile = UserProfile.model_validate(snapshot.to_dict())
        except (GoogleAPICallError, RetryError, GoogleAuthError, ValidationError):
            raise ProfileUnavailableError() from None

        return CurrentUserResponse(**user.model_dump(), profile=profile)

    def register_user(self, user: AuthenticatedUser) -> CurrentUserResponse:
        """Create users/{uid} only if it does not exist; an existing profile is never changed."""
        self._validate_profile_uid(user.uid)

        try:
            reference = self._db.collection("users").document(user.uid)
            try:
                reference.create({"created_at": SERVER_TIMESTAMP, "credits": 0})
            except AlreadyExists:
                raise ProfileAlreadyExistsError() from None
            snapshot = reference.get()
            if not snapshot.exists:
                raise ProfileUnavailableError()
            profile = UserProfile.model_validate(snapshot.to_dict())
        except (GoogleAPICallError, RetryError, GoogleAuthError, ValidationError):
            raise ProfileUnavailableError() from None

        return CurrentUserResponse(**user.model_dump(), profile=profile)
