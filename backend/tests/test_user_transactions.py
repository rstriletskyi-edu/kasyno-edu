from collections.abc import Callable
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import Aborted, PermissionDenied, RetryError
from google.auth.exceptions import GoogleAuthError
from google.cloud.firestore import SERVER_TIMESTAMP

from src.models.auth import AuthenticatedUser
from src.services.user_service import UserService
from src.utils.exceptions import (
    AuthenticationError,
    InsufficientCreditsError,
    ProfileUnavailableError,
)


class FakeTransactionRef:
    """Simulated Firestore document reference under users/{uid}/transactions."""

    def __init__(self, doc_id: str, state: dict[str, object]) -> None:
        self.id = doc_id
        self._state = state

    def create(self, data: dict[str, object]) -> None:
        self._state["direct_transactions"].append((self.id, dict(data)))


class FakeTransaction:
    """In-memory Transaction compatible with google.cloud.firestore.transactional.

    Intentionally omits `.get()` so any regression back to `transaction.get(ref)`
    fails immediately instead of hiding the SDK generator bug.
    """

    def __init__(
        self,
        state: dict[str, object],
        commit_errors: list[Exception] | None = None,
        on_retry: Callable[[int, dict[str, object]], None] | None = None,
    ) -> None:
        self._state = state
        self._commit_errors = list(commit_errors or [])
        self._on_retry = on_retry
        self._max_attempts = 5
        self._read_only = False
        self._id = b"fake-tx-id"
        self.attempts = 0
        self.updates: list[tuple[object, dict[str, object]]] = []
        self.creates: list[tuple[FakeTransactionRef, dict[str, object]]] = []
        self.committed = False
        self.rolled_back = False

    def _clean_up(self) -> None:
        self.updates.clear()
        self.creates.clear()

    def _begin(self, retry_id: object = None) -> None:
        self.attempts += 1

    def update(self, reference: object, fields: dict[str, object]) -> None:
        self.updates.append((reference, dict(fields)))

    def create(self, reference: FakeTransactionRef, data: dict[str, object]) -> None:
        self.creates.append((reference, dict(data)))

    def _commit(self) -> None:
        if self._commit_errors:
            err = self._commit_errors.pop(0)
            if self._on_retry is not None:
                self._on_retry(self.attempts, self._state)
            raise err
        for _ref, fields in self.updates:
            self._state["credits"] = fields["credits"]
        for ref, data in self.creates:
            self._state["transactions"].append((ref.id, data))
        self.committed = True

    def _rollback(self) -> None:
        self.updates.clear()
        self.creates.clear()
        self.rolled_back = True


class FakeTransactionsCollection:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state

    def document(self) -> FakeTransactionRef:
        seq = self._state["next_tx_id"]
        self._state["next_tx_id"] = seq + 1
        return FakeTransactionRef(f"tx-{seq}", self._state)


class FakeUserDocument:
    def __init__(self, state: dict[str, object]) -> None:
        self._state = state
        self.seen_transactions: list[object] = []

    def get(self, transaction: FakeTransaction | None = None) -> Mock:
        self.seen_transactions.append(transaction)
        error = self._state.get("get_error")
        if error is not None:
            raise error
        snapshot = Mock(exists=self._state["exists"])
        if self._state["exists"]:
            snapshot.to_dict.return_value = dict(self._state["doc_data"])
            if "credits" in self._state:
                snapshot.to_dict.return_value["credits"] = self._state["credits"]
        else:
            snapshot.to_dict.return_value = None
        return snapshot

    def collection(self, name: str) -> FakeTransactionsCollection:
        assert name == "transactions"
        return FakeTransactionsCollection(self._state)


class FakeFirestoreDB:
    def __init__(
        self,
        credits: int = 500,
        exists: bool = True,
        include_credits_field: bool = True,
        commit_errors: list[Exception] | None = None,
        on_retry: Callable[[int, dict[str, object]], None] | None = None,
    ) -> None:
        doc_data: dict[str, object] = {}
        self.state: dict[str, object] = {
            "exists": exists,
            "doc_data": doc_data,
            "transactions": [],
            "direct_transactions": [],
            "next_tx_id": 1,
            "get_error": None,
        }
        if include_credits_field:
            self.state["credits"] = credits
        self.seen_uids: list[str] = []
        self.transactions: list[FakeTransaction] = []
        self._commit_errors = commit_errors
        self._on_retry = on_retry
        self.user_doc = FakeUserDocument(self.state)

    def collection(self, name: str) -> Mock:
        assert name == "users"
        users_col = Mock()

        def get_doc(uid: str) -> FakeUserDocument:
            self.seen_uids.append(uid)
            return self.user_doc

        users_col.document.side_effect = get_doc
        return users_col

    def transaction(self) -> FakeTransaction:
        tx = FakeTransaction(
            self.state,
            commit_errors=self._commit_errors,
            on_retry=self._on_retry,
        )
        self.transactions.append(tx)
        return tx


def make_user(uid: str = "user-123") -> AuthenticatedUser:
    return AuthenticatedUser(uid=uid, email_verified=True)


# --- add_credits & remove_credits ---


def test_add_credits_updates_balance_and_logs_transaction_atomically() -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)

    service.add_credits(make_user(), 25, "Ocena fiszki")

    assert db.seen_uids == ["user-123"]
    assert db.state["credits"] == 125.0
    assert len(db.transactions) == 1
    assert db.transactions[0].committed is True
    assert db.transactions[0].rolled_back is False
    assert db.user_doc.seen_transactions == [db.transactions[0]]
    assert db.state["transactions"] == [
        ("tx-1", {"value": 25.0, "Reason": "Ocena fiszki", "timestamp": SERVER_TIMESTAMP})
    ]


def test_remove_credits_subtracts_balance_and_logs_negative_transaction() -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)

    service.remove_credits(make_user(), 30, "Wykorzystanie gry")

    assert db.state["credits"] == 70.0
    assert db.transactions[0].committed is True
    assert db.state["transactions"] == [
        ("tx-1", {"value": -30.0, "Reason": "Wykorzystanie gry", "timestamp": SERVER_TIMESTAMP})
    ]


def test_sequential_add_and_remove_credits_accumulate_distinct_transactions() -> None:
    db = FakeFirestoreDB(credits=50)
    service = UserService(db)
    user = make_user()

    service.add_credits(user, 10.5, "Bonus 1")
    service.remove_credits(user, 5.5, "Opłata")
    service.add_credits(user, 20, "Bonus 2")

    assert db.state["credits"] == 75.0
    assert db.state["transactions"] == [
        ("tx-1", {"value": 10.5, "Reason": "Bonus 1", "timestamp": SERVER_TIMESTAMP}),
        ("tx-2", {"value": -5.5, "Reason": "Opłata", "timestamp": SERVER_TIMESTAMP}),
        ("tx-3", {"value": 20.0, "Reason": "Bonus 2", "timestamp": SERVER_TIMESTAMP}),
    ]


@pytest.mark.parametrize("bad_amount", [0, -1, -0.5, True, False, float("nan"), float("inf"), float("-inf"), "10"])
def test_add_and_remove_credits_reject_invalid_amounts_before_firestore(
    bad_amount: object,
) -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)
    user = make_user()

    with pytest.raises(ValueError):
        service.add_credits(user, bad_amount, "Bad add")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        service.remove_credits(user, bad_amount, "Bad remove")  # type: ignore[arg-type]

    assert db.seen_uids == []
    assert db.transactions == []


@pytest.mark.parametrize("bad_uid", ["a/b", ".", ".."])
def test_credit_and_transaction_methods_reject_unsafe_uids(bad_uid: str) -> None:
    db = FakeFirestoreDB(credits=100)
    service = UserService(db)
    user = make_user(bad_uid)

    with pytest.raises(AuthenticationError):
        service.add_credits(user, 10, "reason")
    with pytest.raises(AuthenticationError):
        service.remove_credits(user, 10, "reason")
    with pytest.raises(AuthenticationError):
        service.get_credits(user)
    with pytest.raises(AuthenticationError):
        service.record_transaction(bad_uid, 10, "reason")
    with pytest.raises(AuthenticationError):
        service.settle_game_wager(user, 10, 0, "bet", "win")

    assert db.seen_uids == []


# --- get_credits & record_transaction ---


def test_get_credits_handles_existing_missing_and_default_profile() -> None:
    assert UserService(FakeFirestoreDB(credits=340)).get_credits(make_user()) == 340
    assert UserService(FakeFirestoreDB(exists=False)).get_credits(make_user()) == 0
    assert (
        UserService(FakeFirestoreDB(include_credits_field=False)).get_credits(make_user()) == 0
    )


def test_record_transaction_writes_expected_schema() -> None:
    db = FakeFirestoreDB()
    service = UserService(db)

    service.record_transaction("user-123", -12.5, "Manual adjustment")

    assert db.seen_uids == ["user-123"]
    assert db.state["direct_transactions"] == [
        ("tx-1", {"value": -12.5, "Reason": "Manual adjustment", "timestamp": SERVER_TIMESTAMP})
    ]


# --- settle_game_wager ---


def test_settle_game_wager_winning_spin_logs_bet_and_win_and_returns_int_balance() -> None:
    db = FakeFirestoreDB(credits=500)
    service = UserService(db)

    new_balance = service.settle_game_wager(
        make_user(), bet=25, payout=90, bet_reason="Ruleta: zakład", win_reason="Ruleta: wygrana"
    )

    assert new_balance == 565
    assert isinstance(db.state["credits"], int)
    assert db.state["credits"] == 565
    assert db.transactions[0].committed is True
    assert db.state["transactions"] == [
        ("tx-1", {"value": -25.0, "Reason": "Ruleta: zakład", "timestamp": SERVER_TIMESTAMP}),
        ("tx-2", {"value": 90.0, "Reason": "Ruleta: wygrana", "timestamp": SERVER_TIMESTAMP}),
    ]


def test_settle_game_wager_losing_spin_logs_only_bet() -> None:
    db = FakeFirestoreDB(credits=500)
    service = UserService(db)

    new_balance = service.settle_game_wager(
        make_user(), bet=50, payout=0, bet_reason="Ruleta: zakład", win_reason="Ruleta: wygrana"
    )

    assert new_balance == 450
    assert db.state["credits"] == 450
    assert db.state["transactions"] == [
        ("tx-1", {"value": -50.0, "Reason": "Ruleta: zakład", "timestamp": SERVER_TIMESTAMP})
    ]


def test_settle_game_wager_exact_balance_and_break_even_edges() -> None:
    all_in_db = FakeFirestoreDB(credits=100)
    assert (
        UserService(all_in_db).settle_game_wager(
            make_user(), bet=100, payout=0, bet_reason="bet", win_reason="win"
        )
        == 0
    )
    assert all_in_db.state["credits"] == 0

    even_db = FakeFirestoreDB(credits=100)
    assert (
        UserService(even_db).settle_game_wager(
            make_user(), bet=40, payout=40, bet_reason="bet", win_reason="win"
        )
        == 100
    )
    assert even_db.state["credits"] == 100
    assert [doc["value"] for _id, doc in even_db.state["transactions"]] == [-40.0, 40.0]


def test_settle_game_wager_insufficient_credits_rolls_back_without_writes() -> None:
    db = FakeFirestoreDB(credits=49)
    service = UserService(db)

    with pytest.raises(InsufficientCreditsError):
        service.settle_game_wager(
            make_user(), bet=50, payout=100, bet_reason="bet", win_reason="win"
        )

    assert db.state["credits"] == 49
    assert db.state["transactions"] == []
    assert db.transactions[0].committed is False
    assert db.transactions[0].rolled_back is True


def test_settle_game_wager_missing_profile_raises_503_and_rolls_back() -> None:
    db = FakeFirestoreDB(exists=False)
    service = UserService(db)

    with pytest.raises(ProfileUnavailableError):
        service.settle_game_wager(
            make_user(), bet=10, payout=0, bet_reason="bet", win_reason="win"
        )

    assert db.state["transactions"] == []
    assert db.transactions[0].rolled_back is True


def test_settle_game_wager_retries_on_aborted_contention_without_duplicate_transactions() -> None:
    def concurrent_deduction(attempt: int, state: dict[str, object]) -> None:
        if attempt == 1:
            # Another concurrent request reduced credits from 500 -> 450 before retry.
            state["credits"] = 450

    db = FakeFirestoreDB(
        credits=500,
        commit_errors=[Aborted("concurrent write")],
        on_retry=concurrent_deduction,
    )
    service = UserService(db)

    new_balance = service.settle_game_wager(
        make_user(), bet=20, payout=40, bet_reason="bet", win_reason="win"
    )

    assert db.transactions[0].attempts == 2
    assert db.transactions[0].committed is True
    assert new_balance == 470
    assert db.state["credits"] == 470
    # Only the committed attempt's two transaction docs exist, with fresh IDs.
    assert db.state["transactions"] == [
        ("tx-3", {"value": -20.0, "Reason": "bet", "timestamp": SERVER_TIMESTAMP}),
        ("tx-4", {"value": 40.0, "Reason": "win", "timestamp": SERVER_TIMESTAMP}),
    ]


def test_settle_game_wager_aborted_retry_prevents_double_spend() -> None:
    def concurrent_spend(attempt: int, state: dict[str, object]) -> None:
        if attempt == 1:
            # Concurrent spin spent 50 of 100 credits, leaving 50 < bet (80).
            state["credits"] = 50

    db = FakeFirestoreDB(
        credits=100,
        commit_errors=[Aborted("concurrent write")],
        on_retry=concurrent_spend,
    )
    service = UserService(db)

    with pytest.raises(InsufficientCreditsError):
        service.settle_game_wager(
            make_user(), bet=80, payout=160, bet_reason="bet", win_reason="win"
        )

    assert db.transactions[0].attempts == 2
    assert db.transactions[0].committed is False
    assert db.transactions[0].rolled_back is True
    assert db.state["credits"] == 50
    assert db.state["transactions"] == []


@pytest.mark.parametrize(
    "error",
    [
        PermissionDenied("firestore permission denied"),
        RetryError("deadline exceeded", cause=RuntimeError("timeout")),
        GoogleAuthError("invalid service credentials"),
    ],
)
def test_settle_game_wager_maps_firestore_errors_to_profile_unavailable(
    error: Exception,
) -> None:
    db = FakeFirestoreDB(credits=500)
    db.state["get_error"] = error
    service = UserService(db)

    with pytest.raises(ProfileUnavailableError):
        service.settle_game_wager(
            make_user(), bet=10, payout=0, bet_reason="bet", win_reason="win"
        )

    assert db.transactions[0].rolled_back is True
