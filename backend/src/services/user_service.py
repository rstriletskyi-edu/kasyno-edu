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
    InsufficientCreditsError,
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

    @staticmethod
    def _transaction_document(value: float, reason: str) -> dict[str, object]:
        return {
            "value": float(value),
            "Reason": reason,
            "timestamp": SERVER_TIMESTAMP,
        }

    def _validate_uid(self, uid: str) -> None:
        # Firebase custom UIDs can contain slashes, but a document ID cannot.
        # Never let a UID select a nested Firestore path.
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

        @firestore.transactional
        def modify(transaction, reference, signed_amount):
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                raise ProfileUnavailableError()
            data = snapshot.to_dict() or {}
            current_credits = data.get("credits", 0)
            transaction.update(
                reference,
                {"credits": current_credits + signed_amount},
            )
            transaction_reference = reference.collection("transactions").document()
            transaction.create(
                transaction_reference,
                self._transaction_document(signed_amount, reason),
            )

        try:
            transaction = self._db.transaction()
            modify(transaction, user_reference, signed_amount)
        except (GoogleAPICallError, RetryError, GoogleAuthError):
            raise ProfileUnavailableError() from None

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

    def settle_game_wager(
        self,
        user: AuthenticatedUser,
        bet: int,
        payout: int,
        bet_reason: str,
        win_reason: str,
    ) -> int:
        """Atomically verify balance, deduct wager, credit payout, and log transactions."""
        if isinstance(bet, bool) or not isinstance(bet, int) or bet <= 0:
            raise ValueError("Bet amount must be a positive integer")
        if isinstance(payout, bool) or not isinstance(payout, int) or payout < 0:
            raise ValueError("Payout amount must be a non-negative integer")
        self._validate_uid(user.uid)

        user_reference = self._db.collection("users").document(user.uid)

        @firestore.transactional
        def settle(transaction, reference) -> int:
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                raise ProfileUnavailableError()
            data = snapshot.to_dict() or {}
            current_credits = int(data.get("credits", 0))
            if current_credits < bet:
                raise InsufficientCreditsError()
            new_credits = current_credits - bet + payout
            transaction.update(reference, {"credits": new_credits})
            transactions = reference.collection("transactions")
            transaction.create(
                transactions.document(),
                self._transaction_document(-bet, bet_reason),
            )
            if payout > 0:
                transaction.create(
                    transactions.document(),
                    self._transaction_document(payout, win_reason),
                )
            return new_credits

        try:
            transaction = self._db.transaction()
            return settle(transaction, user_reference)
        except (GoogleAPICallError, RetryError, GoogleAuthError):
            raise ProfileUnavailableError() from None

    def deduct_game_wager(
        self,
        user: AuthenticatedUser,
        amount: int,
        reason: str,
    ) -> int:
        """Atomically verify balance, deduct an upfront wager, and log the debit."""
        return self.settle_game_wager(
            user,
            bet=amount,
            payout=0,
            bet_reason=reason,
            win_reason="",
        )

    def credit_game_payout(
        self,
        user: AuthenticatedUser,
        amount: int,
        reason: str,
    ) -> int:
        """Atomically credit a positive payout or refund and log the transaction."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("Payout amount must be a positive integer")
        self._validate_uid(user.uid)

        user_reference = self._db.collection("users").document(user.uid)

        @firestore.transactional
        def credit(transaction, reference) -> int:
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                raise ProfileUnavailableError()
            data = snapshot.to_dict() or {}
            current_credits = int(data.get("credits", 0))
            new_credits = current_credits + amount
            transaction.update(reference, {"credits": new_credits})
            transaction.create(
                reference.collection("transactions").document(),
                self._transaction_document(amount, reason),
            )
            return new_credits

        try:
            transaction = self._db.transaction()
            return credit(transaction, user_reference)
        except (GoogleAPICallError, RetryError, GoogleAuthError):
            raise ProfileUnavailableError() from None

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
        self._validate_uid(uid)

        reference = (
            self._db.collection("users")
            .document(uid)
            .collection("transactions")
            .document()
        )
        reference.create(self._transaction_document(value, reason))

    def get_current_user(self, user: AuthenticatedUser) -> CurrentUserResponse:
        """Read-only: never creates or modifies users/{uid}."""
        self._validate_uid(user.uid)

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
        self._validate_uid(user.uid)

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
